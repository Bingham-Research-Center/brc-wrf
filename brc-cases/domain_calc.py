#!/usr/bin/env python3
"""Compute a WRF nested-domain ladder from a physical description, and check it.

The input is a small TOML spec saying *what you want covered* -- a bounding box for
the finest domain, a grid-spacing ladder, and a coarse-domain size -- and the output
is the `&geogrid` geometry that delivers it, plus the checks that catch the mistakes
this repo has actually hit.

    python brc-cases/domain_calc.py brc-cases/specs/<name>.domain.toml
    python brc-cases/domain_calc.py <spec> --namelist-wps /path/to/namelist.wps

Nothing here touches WPS, GRIB, NetCDF, Slurm, or the network. It is arithmetic on
a map projection, and it is deliberately cheap so that domain geometry can be
iterated before anything expensive runs. The authoritative check on the result is
still a geogrid-only preview PNG (BRC-WRF-DOMAIN-PREVIEW-SOP.md) -- this tool tells
you the numbers are self-consistent, not that the terrain is where you think.

Checks applied, and why each exists:

* nest dimensions satisfy ``(e - 1) % parent_grid_ratio == 0`` -- WRF requires the
  nest to tile the parent exactly.
* odd parent_grid_ratio -- even ratios misbehave with feedback.
* every nest keeps a stated margin from its parent's boundary, beyond the
  relaxation zone. A nest touching the parent rim ingests boundary noise.
* the finest domain actually contains the named waypoints. A sibling experiment
  put its target canyon 1.3 km OUTSIDE the intended nest with a placeholder
  placement; this is that failure, made cheap to catch.
* the time-step ladder is reported against the ~6*dx(km) advective guideline, with
  parent_time_step_ratio free to differ from parent_grid_ratio.
* cost is projected as sum(points / dt), scaled from a measured reference run.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

try:
    from pyproj import CRS, Transformer
except ImportError:  # pragma: no cover - environment guard
    sys.exit("domain_calc requires pyproj (env: brc-tools-2026)")


# A measured reference so cost is anchored to something real rather than guessed.
# 20250128-ashley-drainage-wrf gate E: five domains, e_vert=80, time_step=6 with
# 3:1 time ratios, measured 36.4 wall-h per simulated hour at steady state.
# e_vert cancels when the compared configuration also uses 80 levels.
REFERENCE = {
    "label": "20250128-ashley-drainage-wrf gate E (37 m, 5 domains, 80 levels)",
    "wall_h_per_sim_h": 36.4,
    # sum over domains of (horizontal points / dt seconds)
    "work_units": 292681 / (6 / 81) + 202700 / (6 / 27) + 60000 / (6 / 9),
}


@dataclass
class Domain:
    grid_id: int
    parent_id: int
    parent_grid_ratio: int
    parent_time_step_ratio: int
    dx: float
    e_we: int
    e_sn: int
    i_parent_start: int
    j_parent_start: int
    dt: float

    @property
    def points(self) -> int:
        return self.e_we * self.e_sn

    @property
    def width_km(self) -> float:
        return (self.e_we - 1) * self.dx / 1000.0

    @property
    def height_km(self) -> float:
        return (self.e_sn - 1) * self.dx / 1000.0


@dataclass
class Finding:
    level: str  # ERROR | WARN | INFO
    text: str


@dataclass
class Result:
    domains: list[Domain]
    findings: list[Finding] = field(default_factory=list)
    proj: dict = field(default_factory=dict)

    @property
    def failed(self) -> bool:
        return any(f.level == "ERROR" for f in self.findings)


def _round_up_to_nest(cells: float, ratio: int) -> int:
    """Smallest e_we/e_sn >= cells+1 satisfying (e - 1) % ratio == 0."""
    n = int(cells) + 1
    while (n - 1) % ratio != 0:
        n += 1
    return n


def build(spec: dict) -> Result:
    grid = spec["grid"]
    target = spec["target"]

    dxs = [float(v) for v in grid["dx"]]
    ratios = [1] + [int(v) for v in grid["parent_grid_ratio"][1:]]
    t_ratios = [1] + [int(v) for v in grid.get("parent_time_step_ratio", ratios)[1:]]
    ndom = len(dxs)

    findings: list[Finding] = []

    for i in range(1, ndom):
        implied = dxs[i - 1] / dxs[i]
        if abs(implied - ratios[i]) > 1e-6:
            findings.append(Finding(
                "ERROR",
                f"d0{i+1}: dx ladder implies ratio {implied:.3f} but "
                f"parent_grid_ratio is {ratios[i]}",
            ))
        if ratios[i] % 2 == 0:
            findings.append(Finding(
                "WARN",
                f"d0{i+1}: parent_grid_ratio {ratios[i]} is even; odd ratios are "
                "recommended (even ratios misbehave with feedback)",
            ))

    # --- projection: match what WPS will build from these namelist values -------
    ref_lat = float(grid["ref_lat"])
    ref_lon = float(grid["ref_lon"])
    truelat1 = float(grid.get("truelat1", 30.0))
    truelat2 = float(grid.get("truelat2", 60.0))
    stand_lon = float(grid.get("stand_lon", ref_lon))

    crs = CRS.from_proj4(
        f"+proj=lcc +lat_1={truelat1} +lat_2={truelat2} "
        f"+lat_0={ref_lat} +lon_0={stand_lon} +a=6370000 +b=6370000 +units=m +no_defs"
    )
    to_xy = Transformer.from_crs("EPSG:4326", crs, always_xy=True)

    def xy(lon: float, lat: float) -> tuple[float, float]:
        return to_xy.transform(lon, lat)

    # --- finest domain sized to the target box ---------------------------------
    west, south, east, north = (float(v) for v in target["bbox"])
    corners = [xy(west, south), xy(east, south), xy(west, north), xy(east, north)]
    x0 = min(c[0] for c in corners)
    x1 = max(c[0] for c in corners)
    y0 = min(c[1] for c in corners)
    y1 = max(c[1] for c in corners)

    fine_dx = dxs[-1]
    fine_ratio = ratios[-1]
    e_we_fine = _round_up_to_nest((x1 - x0) / fine_dx, fine_ratio)
    e_sn_fine = _round_up_to_nest((y1 - y0) / fine_dx, fine_ratio)
    fine_cx = (x0 + x1) / 2.0
    fine_cy = (y0 + y1) / 2.0

    # --- coarse domain ---------------------------------------------------------
    d01 = spec["coarse"]
    e_we = [int(d01["e_we"])] + [0] * (ndom - 1)
    e_sn = [int(d01["e_sn"])] + [0] * (ndom - 1)
    e_we[-1], e_sn[-1] = e_we_fine, e_sn_fine

    # Intermediate domains: wrap the child with a stated margin, in parent cells.
    margin = int(grid.get("nest_margin_cells", 30))
    for i in range(ndom - 2, 0, -1):
        child_span_x = (e_we[i + 1] - 1) * dxs[i + 1] / dxs[i]
        child_span_y = (e_sn[i + 1] - 1) * dxs[i + 1] / dxs[i]
        if "e_we" in spec.get(f"d0{i+1}", {}):
            e_we[i] = int(spec[f"d0{i+1}"]["e_we"])
            e_sn[i] = int(spec[f"d0{i+1}"]["e_sn"])
        else:
            e_we[i] = _round_up_to_nest(child_span_x + 2 * margin, ratios[i])
            e_sn[i] = _round_up_to_nest(child_span_y + 2 * margin, ratios[i])

    # --- placement: work outward from the finest domain's target centre --------
    # d01 is centred on ref_lat/ref_lon by construction (WPS behaviour).
    centres_x = [0.0] * ndom
    centres_y = [0.0] * ndom
    centres_x[0] = 0.0
    centres_y[0] = 0.0
    centres_x[-1] = fine_cx
    centres_y[-1] = fine_cy
    for i in range(1, ndom - 1):
        # An intermediate domain defaults to wrapping its child, but may declare its
        # own centre when it has a science role of its own rather than merely being
        # a stepping stone. d02 here must span the Basin, which is not the same box
        # as the drainage nest it also has to contain.
        own = spec.get(f"d0{i+1}", {}).get("center")
        if own:
            centres_x[i], centres_y[i] = xy(float(own[0]), float(own[1]))
        else:
            centres_x[i] = fine_cx
            centres_y[i] = fine_cy

    i_start = [1] * ndom
    j_start = [1] * ndom
    for i in range(1, ndom):
        parent_dx = dxs[i - 1]
        # parent centre in projection metres
        pcx, pcy = centres_x[i - 1], centres_y[i - 1]
        parent_w = (e_we[i - 1] - 1) * parent_dx
        parent_h = (e_sn[i - 1] - 1) * parent_dx
        parent_x0 = pcx - parent_w / 2.0
        parent_y0 = pcy - parent_h / 2.0

        child_w = (e_we[i] - 1) * dxs[i]
        child_h = (e_sn[i] - 1) * dxs[i]
        child_x0 = centres_x[i] - child_w / 2.0
        child_y0 = centres_y[i] - child_h / 2.0

        i_start[i] = int(round((child_x0 - parent_x0) / parent_dx)) + 1
        j_start[i] = int(round((child_y0 - parent_y0) / parent_dx)) + 1

        # snap the realised centre so the next level nests against truth
        centres_x[i] = parent_x0 + (i_start[i] - 1) * parent_dx + child_w / 2.0
        centres_y[i] = parent_y0 + (j_start[i] - 1) * parent_dx + child_h / 2.0

    # --- time steps ------------------------------------------------------------
    dt0 = float(grid["time_step"])
    dts = [dt0]
    for i in range(1, ndom):
        dts.append(dts[i - 1] / t_ratios[i])

    domains = [
        Domain(
            grid_id=i + 1,
            parent_id=1 if i == 0 else i,
            parent_grid_ratio=ratios[i],
            parent_time_step_ratio=t_ratios[i],
            dx=dxs[i],
            e_we=e_we[i],
            e_sn=e_sn[i],
            i_parent_start=i_start[i],
            j_parent_start=j_start[i],
            dt=dts[i],
        )
        for i in range(ndom)
    ]

    # --- checks ----------------------------------------------------------------
    for i in range(1, ndom):
        d = domains[i]
        p = domains[i - 1]
        if (d.e_we - 1) % d.parent_grid_ratio:
            findings.append(Finding("ERROR", f"d0{i+1}: (e_we-1)={d.e_we-1} not divisible by {d.parent_grid_ratio}"))
        if (d.e_sn - 1) % d.parent_grid_ratio:
            findings.append(Finding("ERROR", f"d0{i+1}: (e_sn-1)={d.e_sn-1} not divisible by {d.parent_grid_ratio}"))

        span_i = (d.e_we - 1) // d.parent_grid_ratio
        span_j = (d.e_sn - 1) // d.parent_grid_ratio
        left = d.i_parent_start - 1
        right = p.e_we - (d.i_parent_start + span_i)
        bottom = d.j_parent_start - 1
        top = p.e_sn - (d.j_parent_start + span_j)
        worst = min(left, right, bottom, top)
        if worst < 0:
            findings.append(Finding("ERROR", f"d0{i+1}: extends outside d0{i} (margin {worst} cells)"))
        elif worst < 5:
            findings.append(Finding("ERROR", f"d0{i+1}: only {worst} parent cells from the d0{i} boundary; the relaxation zone alone is 4-5"))
        elif worst < margin // 3:
            findings.append(Finding("WARN", f"d0{i+1}: {worst} parent cells ({worst*p.dx/1000:.1f} km) from the d0{i} boundary is tight"))
        else:
            findings.append(Finding("INFO", f"d0{i+1}: margin to d0{i} boundary {worst} cells ({worst*p.dx/1000:.1f} km)"))

    # waypoint containment on the finest domain
    fine = domains[-1]
    fw = (fine.e_we - 1) * fine.dx
    fh = (fine.e_sn - 1) * fine.dx
    fx0, fy0 = centres_x[-1] - fw / 2.0, centres_y[-1] - fh / 2.0
    for name, (wlon, wlat) in target.get("waypoints", {}).items():
        wx, wy = xy(float(wlon), float(wlat))
        inset = min(wx - fx0, fx0 + fw - wx, wy - fy0, fy0 + fh - wy) / 1000.0
        if inset < 0:
            findings.append(Finding("ERROR", f"waypoint '{name}' is {abs(inset):.1f} km OUTSIDE d0{ndom}"))
        elif inset < float(target.get("waypoint_min_inset_km", 2.0)):
            findings.append(Finding("WARN", f"waypoint '{name}' only {inset:.1f} km inside the d0{ndom} edge"))
        else:
            findings.append(Finding("INFO", f"waypoint '{name}' {inset:.1f} km inside d0{ndom}"))

    # time-step guideline
    for d in domains:
        guide = 6.0 * d.dx / 1000.0
        if d.dt > guide:
            findings.append(Finding("WARN", f"d0{d.grid_id}: dt {d.dt:.3f} s exceeds the ~6*dx guideline ({guide:.2f} s)"))
        else:
            findings.append(Finding("INFO", f"d0{d.grid_id}: dt {d.dt:.3f} s vs ~6*dx guideline {guide:.2f} s ({100*d.dt/guide:.0f}%)"))

    return Result(domains=domains, findings=findings, proj={
        "ref_lat": ref_lat, "ref_lon": ref_lon, "truelat1": truelat1,
        "truelat2": truelat2, "stand_lon": stand_lon, "dx": dxs[0],
    })


def cost(result: Result) -> tuple[float, list[tuple[int, float]]]:
    units = [(d.grid_id, d.points / d.dt) for d in result.domains]
    total = sum(u for _, u in units)
    wall = REFERENCE["wall_h_per_sim_h"] * total / REFERENCE["work_units"]
    return wall, units


def namelist_geogrid(result: Result, spec: dict) -> str:
    ds = result.domains
    n = len(ds)

    def row(vals, width=6):
        return ",".join(f"{v:>{width}}" for v in vals) + ","

    share = spec.get("share", {})
    start = share.get("start_date", "<UNSET>")
    end = share.get("end_date", "<UNSET>")
    geog_res = spec["grid"].get("geog_data_res", ["default"] * n)

    lines = [
        "&share",
        " wrf_core = 'ARW',",
        f" max_dom = {n},",
        " start_date = " + ",".join(f"'{start}'" for _ in ds) + ",",
        " end_date   = " + ",".join(f"'{end}'" for _ in ds) + ",",
        f" interval_seconds = {share.get('interval_seconds', 3600)},",
        # MUST match nocolons in namelist.input &time_control. The two flags live in
        # different namelists and nothing reconciles them: with nocolons only on the
        # WRF side, WPS writes met_em.d01.2026-04-24_23:00:00.nc while real.exe asks
        # for ...23_00_00.nc and dies with "bad date in namelist or file not in
        # directory". That cost a gate D submission on ashley_drainage_120m.
        *([" nocolons = .true.,"] if share.get("nocolons") else []),
        "/",
        "",
        "&geogrid",
        " parent_id         = " + row([d.parent_id for d in ds]),
        " parent_grid_ratio = " + row([d.parent_grid_ratio for d in ds]),
        " i_parent_start    = " + row([d.i_parent_start for d in ds]),
        " j_parent_start    = " + row([d.j_parent_start for d in ds]),
        " e_we              = " + row([d.e_we for d in ds]),
        " e_sn              = " + row([d.e_sn for d in ds]),
        " geog_data_res     = " + ",".join(f"'{r}'" for r in geog_res) + ",",
        f" dx = {result.proj['dx']:.0f},",
        f" dy = {result.proj['dx']:.0f},",
        " map_proj = 'lambert',",
        f" ref_lat   = {result.proj['ref_lat']},",
        f" ref_lon   = {result.proj['ref_lon']},",
        f" truelat1  = {result.proj['truelat1']},",
        f" truelat2  = {result.proj['truelat2']},",
        f" stand_lon = {result.proj['stand_lon']},",
        f" geog_data_path = '{spec['grid'].get('geog_data_path', '<UNSET>')}',",
        "/",
        "",
        "! &ungrib and &metgrid are STUBS. The values below are placeholders: the WPS",
        "! field-proof job rewrites prefix and fg_name once per stream, in fg_name",
        "! priority order, from the case manifest. They are emitted anyway because the",
        "! rewrite REPLACES these lines and requires exactly one match each -- a template",
        "! carrying only &share and &geogrid makes it die with 'expected one namelist",
        "! replacement for prefix, got 0' after ungrib has already been set up (that is",
        "! job 14393162). Emitting them here keeps the whole file generated: without it",
        "! the operator hand-adds two sections to a file whose header says do not",
        "! hand-edit, and the spec stops describing what ran.",
        "&ungrib",
        " out_format = 'WPS',",
        " prefix = 'FILE',",
        "/",
        "",
        "&metgrid",
        " fg_name = 'FILE',",
        "/",
    ]
    return "\n".join(lines) + "\n"


# Geometry keys in namelist.input's &domains that are DERIVED. Anything not listed
# here (physics, vertical grid, damping) is hand-authored and must not be touched.
SYNCED_KEYS = ("max_dom", "e_we", "e_sn", "dx", "dy", "grid_id", "parent_id",
               "i_parent_start", "j_parent_start", "parent_grid_ratio",
               "parent_time_step_ratio", "time_step")


def sync_namelist_input(result: Result, path: Path) -> list[str]:
    """Rewrite ONLY the derived geometry keys in an existing namelist.input.

    namelist.wps is generated wholesale, but namelist.input carries hand-authored
    physics that must survive. Without this, its &domains block drifts away from the
    spec silently -- the two files then describe different runs and nothing complains.
    Returns the list of lines changed, so the caller can prove what moved.
    """
    ds = result.domains
    vals = {
        "max_dom": [len(ds)],
        "e_we": [d.e_we for d in ds],
        "e_sn": [d.e_sn for d in ds],
        "dx": [int(d.dx) for d in ds],
        "dy": [int(d.dx) for d in ds],
        "grid_id": [d.grid_id for d in ds],
        "parent_id": [d.parent_id for d in ds],
        "i_parent_start": [d.i_parent_start for d in ds],
        "j_parent_start": [d.j_parent_start for d in ds],
        "parent_grid_ratio": [d.parent_grid_ratio for d in ds],
        "parent_time_step_ratio": [d.parent_time_step_ratio for d in ds],
        "time_step": [int(ds[0].dt)],
    }
    changed: list[str] = []
    out: list[str] = []
    for line in path.read_text().splitlines():
        stripped = line.strip()
        key = stripped.split("=")[0].strip() if "=" in stripped else ""
        if key in SYNCED_KEYS and not stripped.startswith("!"):
            new = f" {key:24} = " + ",".join(f"{v:>5}" for v in vals[key]) + ","
            if new.split("=")[1].strip() != line.split("=")[1].strip():
                changed.append(f"{key}: {line.split('=')[1].strip()} -> {new.split('=')[1].strip()}")
            out.append(new)
        else:
            out.append(line)
    path.write_text("\n".join(out) + "\n")
    return changed


def report(result: Result, spec: dict) -> str:
    out = [f"# {spec.get('case', {}).get('name', 'domain')} -- geometry"]
    out.append("")
    out.append(f"{'dom':>4} {'dx':>8} {'e_we':>6} {'e_sn':>6} {'i_str':>6} {'j_str':>6} "
               f"{'km E-W':>8} {'km N-S':>8} {'dt (s)':>8} {'points':>9}")
    for d in result.domains:
        out.append(f"d0{d.grid_id:<3} {d.dx:>8.1f} {d.e_we:>6} {d.e_sn:>6} "
                   f"{d.i_parent_start:>6} {d.j_parent_start:>6} "
                   f"{d.width_km:>8.1f} {d.height_km:>8.1f} {d.dt:>8.3f} {d.points:>9,}")

    wall, units = cost(result)
    total_units = sum(u for _, u in units)
    out.append("")
    out.append("Cost (scaled from a MEASURED reference; an estimate, not a measurement)")
    out.append(f"  reference: {REFERENCE['label']}")
    for gid, u in units:
        out.append(f"  d0{gid}: {100*u/total_units:5.1f}% of work")
    out.append(f"  => ~{wall:.2f} wall-hours per simulated hour")
    run_h = spec.get("run", {}).get("hours")
    if run_h:
        out.append(f"  => ~{wall*float(run_h):.0f} wall-hours for a {run_h} h run")

    out.append("")
    order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    for f in sorted(result.findings, key=lambda f: order[f.level]):
        out.append(f"  {f.level:5} {f.text}")
    out.append("")
    out.append("FAIL: fix the errors above" if result.failed else
               "OK: geometry is self-consistent. A geogrid preview PNG is still required "
               "to confirm the terrain is where you think (DOMAIN-PREVIEW-SOP).")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("spec", type=Path, help="domain spec TOML")
    ap.add_argument("--namelist-wps", type=Path, help="write the &share/&geogrid blocks here")
    ap.add_argument("--sync-namelist-input", type=Path,
                    help="rewrite only the derived geometry keys in an existing "
                         "namelist.input, leaving hand-authored physics untouched")
    args = ap.parse_args(argv)

    spec = tomllib.loads(args.spec.read_text())
    result = build(spec)
    print(report(result, spec))

    if args.namelist_wps:
        if result.failed:
            print(f"\nrefusing to write {args.namelist_wps}: geometry has errors", file=sys.stderr)
            return 2
        header = spec.get("case", {}).get("header", "")
        text = ("".join(f"! {line}\n" for line in header.splitlines()) if header else "")
        text += namelist_geogrid(result, spec)
        args.namelist_wps.parent.mkdir(parents=True, exist_ok=True)
        args.namelist_wps.write_text(text)
        print(f"\nwrote {args.namelist_wps}")

    if args.sync_namelist_input:
        if result.failed:
            print(f"\nrefusing to sync {args.sync_namelist_input}: geometry has errors",
                  file=sys.stderr)
            return 2
        changed = sync_namelist_input(result, args.sync_namelist_input)
        print(f"\nsynced geometry into {args.sync_namelist_input}")
        for c in changed:
            print(f"  {c}")
        if not changed:
            print("  (already in sync)")

    return 2 if result.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
