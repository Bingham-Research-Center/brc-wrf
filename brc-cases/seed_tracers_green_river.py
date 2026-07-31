"""Seed eight source-region tracers for green_river_600m.

Replaces WRF's tracer test blob. With tracer_opt=2 and no seeding, WRF sets
tr17_1..4 to 1.0 in a 9x9 block at the DOMAIN CENTRE on the lowest levels, which
here would inject a meaningless blob in the middle of the Uintas.

THE TRACERS ARE PASSIVE. They are advected and mixed but exert no force, so a
seeding choice cannot change the flow. It only changes what can be ASKED of the
output afterwards -- which for this experiment is the whole question: is the
lowest 2 km one drainage layer, or a stack from distinguishable sources?

HOW THE REGIONS ARE DEFINED, and why it matters. Wherever possible a region is
cut from the model's OWN fields -- LANDMASK for the reservoir, HGT for slope and
floor -- so it is objective rather than drawn by eye. Where a coordinate box is
needed it is anchored on a real station position from brc-tools lookups.toml.
These boxes are EXPERIMENT CONFIGURATION, not geography: they say which slab of
this domain to label, and they must never be read back as "where Browns Park is".
The corridor's unnamed landmarks are deliberately absent from lookups.toml
because no gazetteer source was available (CHK-GEOG), and that restraint is not
undone here.

    python -B seed_tracers_green_river.py wrfinput_d01 wrfinput_d02

THE SOURCE AREAS ARE NOT EQUAL, and the analysis must not pretend they are.
Measured on d02: Wyoming approach 8459 km2, Uinta north slope 2666, Yampa 1768,
Ashley floor 1109, Blue Mountain 908, Diamond Mountain 650, Browns Park 387,
reservoir 207. A region 40x larger labels 40x more air, so RAW concentrations at
the reading sections cannot be compared between tracers and must never be read as
"source X dominates". What the comparison IS valid for is the thing the question
actually asks: the HEIGHT at which each tracer arrives. Area scales a tracer's
magnitude; it does not move the layer it occupies. Any claim about relative source
strength needs area normalisation stated explicitly.

Idempotent: it always writes the full field, so re-running does not accumulate.
Fails loudly if any tracer would be seeded into ZERO cells -- an empty source
region is a silent nothing in the output, and it is the failure this experiment
would be least likely to notice.
"""
from __future__ import annotations

import sys

import numpy as np
from netCDF4 import Dataset

G = 9.81
SEED_DEPTH_M = 300.0        # depth AGL of the seeded layer, as the sibling used

TRACERS = ("tr17_1", "tr17_2", "tr17_3", "tr17_4",
           "tr17_5", "tr17_6", "tr17_7", "tr17_8")

# lon0, lon1, lat0, lat1
BOX = {
    "reservoir":  (-109.80, -109.25, 40.80, 41.55),   # Flaming Gorge + Red Canyon
    "wyoming":    (-110.40, -108.60, 41.35, 41.95),   # the approach north of it
    "browns":     (-109.25, -108.75, 40.72, 40.98),   # trench floor, anchored on KPRU1
    "diamond":    (-109.45, -109.00, 40.52, 40.75),   # plateau, anchored on DIAU1
    "blue_mtn":   (-108.95, -108.30, 40.25, 40.62),   # Colorado side, south of Lodore
    "yampa":      (-108.75, -108.05, 40.30, 40.65),   # the eastern tributary
    "uinta_n":    (-110.40, -109.25, 40.58, 41.00),   # north slope, the coldest source
    "ashley":     (-109.85, -109.35, 40.30, 40.62),   # basin floor, sibling continuity
}
LABEL = {
    "tr17_1": "Flaming Gorge reservoir (LANDMASK water)",
    "tr17_2": "Wyoming approach north of the reservoir",
    "tr17_3": "Browns Park trench floor",
    "tr17_4": "Diamond Mountain plateau",
    "tr17_5": "Blue Mountain / Colorado side",
    "tr17_6": "Yampa valley at Deerlodge",
    "tr17_7": "Uinta north slope",
    "tr17_8": "Ashley Valley floor",
}


def regions(hgt, lat, lon, landmask):
    def box(name):
        lo0, lo1, la0, la1 = BOX[name]
        return (lon >= lo0) & (lon <= lo1) & (lat >= la0) & (lat <= la1)

    return {
        # The reservoir is cut from the model's own land mask, not from a box I drew.
        "tr17_1": box("reservoir") & (landmask < 0.5),
        "tr17_2": box("wyoming") & (hgt < 2200.0),
        "tr17_3": box("browns") & (hgt < 1900.0),
        "tr17_4": box("diamond") & (hgt > 2050.0),
        "tr17_5": box("blue_mtn") & (hgt > 2050.0),
        "tr17_6": box("yampa") & (hgt < 2100.0),
        "tr17_7": box("uinta_n") & (hgt > 2600.0),
        "tr17_8": box("ashley") & (hgt < 1900.0),
    }


def seed(path: str) -> int:
    nc = Dataset(path, "a")
    hgt = np.asarray(nc.variables["HGT"][0]).astype("float64")
    lat = np.asarray(nc.variables["XLAT"][0]).astype("float64")
    lon = np.asarray(nc.variables["XLONG"][0]).astype("float64")
    landmask = np.asarray(nc.variables["LANDMASK"][0]).astype("float64")

    ph = np.asarray(nc.variables["PH"][0]).astype("float64")
    phb = np.asarray(nc.variables["PHB"][0]).astype("float64")
    zw = (ph + phb) / G
    zmass = 0.5 * (zw[:-1] + zw[1:])
    agl = zmass - hgt[None, :, :]
    in_layer = agl <= SEED_DEPTH_M

    masks = regions(hgt, lat, lon, landmask)
    print(f"=== {path} ===")
    print(f"  terrain {hgt.min():.0f}-{hgt.max():.0f} m, grid {hgt.shape[1]}x{hgt.shape[0]}, "
          f"water cells {int((landmask < 0.5).sum())}")

    empty = []
    for name in TRACERS:
        if name not in nc.variables:
            print(f"  {name}: <absent from this file>")
            continue
        var = nc.variables[name]
        new = np.zeros_like(np.asarray(var[:]).astype("float64"))
        m2d = masks[name]
        sel = in_layer & m2d[None, :, :]
        new[0][sel] = 1.0
        var[:] = new
        n2d, n3d = int(m2d.sum()), int(sel.sum())
        print(f"  {name}: {n2d:6d} columns, {n3d:8d} cells   [{LABEL[name]}]")
        if n3d == 0:
            empty.append(name)
    nc.close()
    if empty:
        print(f"  ERROR: seeded ZERO cells for {', '.join(empty)} -- "
              f"region does not intersect this domain", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit("usage: seed_tracers_green_river.py <wrfinput_d0N> [...]")
    rc = 0
    for path in sys.argv[1:]:
        rc |= seed(path)
    return rc


if __name__ == "__main__":
    sys.exit(main())
