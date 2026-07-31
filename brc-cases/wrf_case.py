#!/usr/bin/env python3
"""Validate and render BRC WRF case manifests without running WRF.

This is deliberately small and dependency-free. It accepts only the constrained
case-YAML subset documented in ``brc-cases/README.md``.
"""

from __future__ import annotations

import argparse
import ast
import copy
import glob
import json
import os
import subprocess
import re
import shlex
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DATE_FORMAT = "%Y-%m-%d_%H:%M:%S"
CASE_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
DEFAULT_PRACTICAL_TASKS = (16, 28, 56)
PRACTICAL_SLURM_LOG_ROOT = Path(
    "/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_build_logs/brc-wrf"
)
WPS_FIELD_CHECKS = (
    ("3d_height", "^(GHT|HGT)$"),
    ("3d_pressure", "^(PRES|PRESSURE)$"),
    ("3d_temperature", "^TT$"),
    ("3d_humidity", "^(RH|QVAPOR|SPECHUMD)$"),
    ("3d_u_wind", "^UU$"),
    ("3d_v_wind", "^VV$"),
    ("surface_pressure", "^PSFC$"),
    ("sea_level_pressure", "^PMSL$"),
    ("land_mask", "^(LANDSEA|LANDMASK)$"),
    ("terrain", "^(SOILHGT|HGT_M)$"),
    ("soil_temperature_layers", "^(ST|ST[0-9].*|SOILT[0-9].*)$"),
    ("soil_moisture_layers", "^(SM|SM[0-9].*|SOILM[0-9].*)$"),
    ("snow", "^(SNOW|SNOWH)$"),
    ("skin_temperature", "^SKINTEMP$"),
)
REQUIRED_WRF_RUNTIME_FILES = (
    "CAMtr_volume_mixing_ratio",
    "RRTMG_LW_DATA",
    "RRTMG_SW_DATA",
    "ozone.formatted",
    "ozone_lat.formatted",
    "ozone_plev.formatted",
    "GENPARM.TBL",
    "LANDUSE.TBL",
    "SOILPARM.TBL",
    "VEGPARM.TBL",
)
PENDING_NUMERIC_TOKENS = {
    "pending",
    "field_adequacy_pending",
    "metgrid_pending",
    "unknown",
    "tbd",
}
# Same idea as PENDING_NUMERIC_TOKENS, for case.start / case.end when the event has
# not been selected yet. Explicitly NOT a parseable date: a placeholder that parses
# is indistinguishable from a decision.
PENDING_DATE_TOKENS = {
    "pending",
    "event_pending",
    "unknown",
    "tbd",
}

REQUIRED_SECTIONS = {
    "case": ("name", "start", "end", "domains"),
    "forcing": (
        "sources",
        "wps_fg_name",
        "interval_seconds",
        "num_metgrid_levels",
        "manifest_path",
        "contract_path",
    ),
    "paths": (
        "wrf_src",
        "wrf_build",
        "wps_root",
        "input_root",
        "run_root",
        "wps_run",
        "wrf_run",
        "geog_data_path",
        "archive_root",
    ),
    "slurm": (
        "job_name",
        "account",
        "partition",
        "nodes",
        "ntasks",
        "time",
        "memory",
        "mpi_launcher",
    ),
}


@dataclass
class Finding:
    severity: str
    message: str


@dataclass
class PracticalHarnessResult:
    output_dir: Path
    scripts: list[Path]
    packet_files: list[Path]
    prep_scripts: list[Path]


def parse_value(raw: str) -> Any:
    raw = raw.strip()
    if not raw:
        return ""
    if raw.startswith(('"', "'", "[", "{")):
        # JSON first so inline flow values can use real YAML/JSON spelling --
        # true/false/null rather than Python's True/False/None. literal_eval stays as
        # the fallback for single-quoted strings and tuples, which JSON rejects.
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return ast.literal_eval(raw)
    lowered = raw.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none"}:
        return None
    if re.fullmatch(r"[-+]?\d+", raw):
        return int(raw)
    return raw


def load_case(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current: dict[str, Any] | None = None
    current_name: str | None = None

    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        body = line.split("#", 1)[0].rstrip()
        if not body.strip():
            continue
        indent = len(body) - len(body.lstrip(" "))
        if indent == 0:
            if ":" not in body:
                raise ValueError(f"{path}:{line_no}: expected 'key:'")
            key, raw = body.split(":", 1)
            key = key.strip()
            raw = raw.strip()
            if raw:
                data[key] = parse_value(raw)
                current = None
                current_name = None
            else:
                section: dict[str, Any] = {}
                data[key] = section
                current = section
                current_name = key
            continue
        if indent != 2 or current is None or current_name is None:
            raise ValueError(
                f"{path}:{line_no}: only two-space section keys are supported"
            )
        if ":" not in body.lstrip(" "):
            raise ValueError(f"{path}:{line_no}: expected 'key: value'")
        key, raw = body.lstrip(" ").split(":", 1)
        current[key.strip()] = parse_value(raw)
    return data


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def as_path(value: Any) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(str(value))))


def parse_positive_int_setting(
    value: Any,
    label: str,
    findings: list[Finding],
    *,
    allow_pending: bool = False,
    strict_pending: bool = False,
) -> int | None:
    pending = value is None or str(value).strip().lower() in PENDING_NUMERIC_TOKENS
    if pending:
        if allow_pending:
            severity = "ERROR" if strict_pending else "WARN"
        else:
            severity = "ERROR"
        findings.append(
            Finding(
                severity,
                f"{label} is pending; set it from metgrid field proof before real.exe",
            )
        )
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        findings.append(Finding("ERROR", f"{label} must be a positive integer: {value!r}"))
        return None
    if parsed <= 0:
        findings.append(Finding("ERROR", f"{label} must be positive"))
        return None
    return parsed


def path_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def add_path_finding(
    findings: list[Finding],
    path: Path,
    label: str,
    *,
    strict_files: bool,
    must_be_dir: bool | None = None,
) -> None:
    if not path.exists():
        severity = "ERROR" if strict_files else "WARN"
        findings.append(Finding(severity, f"{label} does not exist: {path}"))
        return
    if must_be_dir is True and not path.is_dir():
        findings.append(Finding("ERROR", f"{label} is not a directory: {path}"))
    if must_be_dir is False and not path.is_file():
        findings.append(Finding("ERROR", f"{label} is not a file: {path}"))


def add_wrf_build_findings(
    findings: list[Finding],
    root: Path,
    *,
    strict_files: bool,
) -> None:
    add_path_finding(
        findings,
        root,
        "paths.wrf_build",
        strict_files=strict_files,
        must_be_dir=True,
    )
    if not root.exists() or not root.is_dir():
        return

    severity = "ERROR" if strict_files else "WARN"
    for exe in ("real.exe", "wrf.exe"):
        path = root / "main" / exe
        if not (path.exists() and os.access(path, os.X_OK)):
            findings.append(
                Finding(
                    severity,
                    f"paths.wrf_build missing executable main/{exe}: {path}",
                )
            )

    run_dir = root / "run"
    if not run_dir.is_dir():
        findings.append(Finding(severity, f"paths.wrf_build missing directory run: {run_dir}"))
        return

    for runtime_file in REQUIRED_WRF_RUNTIME_FILES:
        path = run_dir / runtime_file
        if not path.is_file():
            findings.append(
                Finding(
                    severity,
                    f"paths.wrf_build missing runtime file run/{runtime_file}: {path}",
                )
            )


def add_wps_root_findings(
    findings: list[Finding],
    root: Path,
    *,
    strict_files: bool,
    vtable: str,
    vtable_dir: Path | None = None,
) -> None:
    add_path_finding(
        findings,
        root,
        "paths.wps_root",
        strict_files=strict_files,
        must_be_dir=True,
    )
    if not root.exists() or not root.is_dir():
        return

    severity = "ERROR" if strict_files else "WARN"
    for exe in ("geogrid.exe", "ungrib.exe", "metgrid.exe"):
        path = root / exe
        if not (path.exists() and os.access(path, os.X_OK)):
            findings.append(
                Finding(
                    severity,
                    f"paths.wps_root missing top-level executable {exe}: {path}",
                )
            )

    for subdir in ("geogrid", "metgrid", "ungrib"):
        path = root / subdir
        if not path.is_dir():
            findings.append(Finding(severity, f"paths.wps_root missing directory {subdir}: {path}"))

    required_files = ["link_grib.csh"]
    if "/" in vtable or not vtable:
        findings.append(Finding("ERROR", f"wps.vtable is not a simple table name: {vtable!r}"))
    elif vtable_dir is None or not (vtable_dir / vtable).is_file():
        # Only demand it from the WPS tree when the case does NOT carry its own copy.
        # wps.vtable_dir exists precisely because the two-stream HRRR+GFS-soil Vtables
        # ship in neither WPS nor this repo, and warning that a file is "missing" from
        # a directory the run never reads trains the operator to ignore warnings.
        required_files.append(f"ungrib/Variable_Tables/{vtable}")

    for file_name in required_files:
        path = root / file_name
        if not path.is_file():
            findings.append(
                Finding(severity, f"paths.wps_root missing file {file_name}: {path}")
            )

def add_storage_policy_findings(
    findings: list[Finding],
    data: dict[str, Any],
    *,
    strict_files: bool,
) -> None:
    paths = data["paths"]
    repo_root = as_path(paths["wrf_src"])
    for key in ("input_root", "grib_data", "run_root", "wps_run", "wrf_run", "archive_root"):
        if key not in paths:
            continue
        path = as_path(paths[key])
        if path_under(path, repo_root):
            findings.append(
                Finding(
                    "ERROR",
                    f"paths.{key} must not be inside the brc-wrf checkout: {path}",
                )
            )

    archive_root = as_path(paths["archive_root"])
    archive_text = str(archive_root)
    if archive_text.startswith("/scratch/"):
        findings.append(
            Finding("ERROR", f"paths.archive_root must be durable, not scratch: {archive_root}")
        )
    elif "lawson-group6" not in archive_text:
        severity = "ERROR" if strict_files else "WARN"
        findings.append(
            Finding(
                severity,
                "paths.archive_root should be under durable lawson-group6 storage: "
                f"{archive_root}",
            )
        )


def parse_case_datetime(value: Any, field: str, findings: list[Finding]) -> datetime | None:
    text = str(value)
    for fmt in (DATE_FORMAT, "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    # A manifest may legitimately exist before its event is chosen: domain geometry,
    # forcing design and the Slurm profile are all decidable first, and a geogrid
    # preview needs no dates at all. Writing a plausible placeholder instead would
    # record a decision nobody made, so declare the gap the same way an unproven
    # num_metgrid_levels is declared. Downstream steps still refuse -- see
    # run_readiness_findings.
    if text.strip().lower() in PENDING_DATE_TOKENS:
        findings.append(
            Finding("WARN", f"case.{field} is pending; set it when the event is chosen")
        )
        return None
    findings.append(Finding("ERROR", f"case.{field} has unsupported date format: {text}"))
    return None


def parse_namelist_values(path: Path) -> dict[str, list[str]]:
    wanted = {
        "start_date",
        "end_date",
        "interval_seconds",
        "fg_name",
        "geog_data_path",
        "num_metgrid_levels",
    }
    values: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        body = line.split("!", 1)[0]
        if "=" not in body:
            continue
        key, raw = body.split("=", 1)
        key = key.strip()
        if key not in wanted:
            continue
        quoted = re.findall(r"'([^']*)'|\"([^\"]*)\"", raw)
        if quoted:
            values[key] = [a or b for a, b in quoted]
        else:
            values[key] = [v.strip().strip(",") for v in raw.split(",") if v.strip()]
    return values


def parse_memory_gib(value: Any) -> float | None:
    text = str(value).strip().upper()
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([GMTP]?)(?:I?B)?", text)
    if not match:
        return None
    amount = float(match.group(1))
    unit = match.group(2) or "M"
    if unit == "T":
        return amount * 1024
    if unit == "G":
        return amount
    if unit == "M":
        return amount / 1024
    if unit == "P":
        return amount * 1024 * 1024
    return None


def validate_manifest(
    findings: list[Finding],
    path: Path,
    case_name: str,
    sources: list[str],
    strict_files: bool,
) -> None:
    if not path.exists():
        add_path_finding(findings, path, "forcing.manifest_path", strict_files=strict_files)
        return
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        findings.append(Finding("ERROR", f"manifest JSON is invalid: {path}: {exc}"))
        return
    if manifest.get("manifest_kind") != "wrf_input_staging":
        findings.append(Finding("ERROR", f"manifest_kind is not wrf_input_staging: {path}"))
    manifest_case = manifest.get("case", {})
    if manifest_case.get("name") != case_name:
        findings.append(
            Finding(
                "WARN",
                f"manifest case name {manifest_case.get('name')!r} != case.name {case_name!r}",
            )
        )
    manifest_sources = set(as_list(manifest_case.get("sources")))
    missing = set(sources) - manifest_sources
    if missing:
        findings.append(Finding("WARN", f"manifest missing requested sources: {sorted(missing)}"))


def validate_contract(
    findings: list[Finding],
    path: Path,
    case_name: str,
    wps_fg_name: list[str],
    interval_seconds: int,
    strict_files: bool,
) -> None:
    if not path.exists():
        add_path_finding(findings, path, "forcing.contract_path", strict_files=strict_files)
        return
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        findings.append(Finding("ERROR", f"contract JSON is invalid: {path}: {exc}"))
        return
    if contract.get("contract_kind") != "wps_wrf_case_contract":
        findings.append(Finding("ERROR", f"contract_kind is not wps_wrf_case_contract: {path}"))
    if contract.get("case") != case_name:
        findings.append(
            Finding("ERROR", f"contract case {contract.get('case')!r} != {case_name!r}")
        )
    if as_list(contract.get("wps_fg_name")) != wps_fg_name:
        findings.append(
            Finding(
                "ERROR",
                f"contract wps_fg_name {contract.get('wps_fg_name')!r} != {wps_fg_name!r}",
            )
        )
    if contract.get("interval_seconds") != interval_seconds:
        findings.append(
            Finding(
                "ERROR",
                f"contract interval_seconds {contract.get('interval_seconds')!r} != {interval_seconds!r}",
            )
        )


def validate_namelists(
    findings: list[Finding],
    data: dict[str, Any],
    *,
    strict_files: bool,
) -> None:
    namelists = data.get("namelists", {})
    forcing = data["forcing"]
    paths = data["paths"]
    case = data["case"]
    wps = data.get("wps", {})
    start = str(case["start"])
    end = str(case["end"])

    for key in ("namelist_wps", "namelist_input"):
        if key not in namelists:
            continue
        path = as_path(namelists[key])
        if not path.exists():
            add_path_finding(findings, path, key, strict_files=strict_files)
            continue
        values = parse_namelist_values(path)
        if key == "namelist_wps":
            interval = values.get("interval_seconds", [None])[0]
            if interval is not None and int(interval) != int(forcing["interval_seconds"]):
                findings.append(
                    Finding("ERROR", f"{key} interval_seconds {interval} != case value")
                )
            fg_name = values.get("fg_name")
            expected_fg_name = as_list(wps.get("namelist_fg_name", forcing["wps_fg_name"]))
            if fg_name and fg_name != expected_fg_name:
                findings.append(
                    Finding("ERROR", f"{key} fg_name {fg_name!r} != expected {expected_fg_name!r}")
                )
            geog = values.get("geog_data_path", [None])[0]
            if geog and as_path(geog) != as_path(paths["geog_data_path"]):
                findings.append(Finding("ERROR", f"{key} geog_data_path differs from case"))
            starts = values.get("start_date", [])
            ends = values.get("end_date", [])
            if starts and any(v != start for v in starts):
                findings.append(Finding("WARN", f"{key} start_date does not match {start}"))
            if ends and any(v != end for v in ends):
                findings.append(Finding("WARN", f"{key} end_date does not match {end}"))
        if key == "namelist_input":
            levels = values.get("num_metgrid_levels", [None])[0]
            expected_levels = parse_positive_int_setting(
                forcing["num_metgrid_levels"],
                "forcing.num_metgrid_levels",
                findings,
                allow_pending=True,
                strict_pending=strict_files,
            )
            if levels is not None and expected_levels is not None and int(levels) != expected_levels:
                findings.append(
                    Finding("ERROR", f"{key} num_metgrid_levels {levels} != case value")
                )


def validate_case(data: dict[str, Any], *, strict_files: bool) -> list[Finding]:
    findings: list[Finding] = []

    for section, keys in REQUIRED_SECTIONS.items():
        if section not in data or not isinstance(data[section], dict):
            findings.append(Finding("ERROR", f"missing section: {section}"))
            continue
        for key in keys:
            if key not in data[section]:
                findings.append(Finding("ERROR", f"missing required key: {section}.{key}"))
    if any(f.severity == "ERROR" for f in findings):
        return findings

    case = data["case"]
    forcing = data["forcing"]
    paths = data["paths"]
    slurm = data["slurm"]
    wps = data.get("wps", {})

    case_name = str(case["name"])
    if not CASE_NAME_RE.match(case_name):
        findings.append(Finding("ERROR", f"case.name is not path-safe: {case_name!r}"))

    start = parse_case_datetime(case["start"], "start", findings)
    end = parse_case_datetime(case["end"], "end", findings)
    if start and end and start >= end:
        findings.append(Finding("ERROR", "case.start must be before case.end"))

    domains = int(case["domains"])
    if domains < 1:
        findings.append(Finding("ERROR", "case.domains must be >= 1"))

    sources = [str(v) for v in as_list(forcing["sources"])]
    wps_fg_name = [str(v) for v in as_list(forcing["wps_fg_name"])]
    interval_seconds = int(forcing["interval_seconds"])
    artifact_case_name = str(forcing.get("artifact_case_name", case_name))
    if not CASE_NAME_RE.match(artifact_case_name):
        findings.append(
            Finding(
                "ERROR",
                f"forcing.artifact_case_name is not path-safe: {artifact_case_name!r}",
            )
        )
    parse_positive_int_setting(
        forcing["num_metgrid_levels"],
        "forcing.num_metgrid_levels",
        findings,
        allow_pending=True,
        strict_pending=strict_files,
    )

    if sources == ["nam_analysis"] and wps_fg_name != ["NAM"]:
        findings.append(Finding("ERROR", "NAM-only source should use wps_fg_name ['NAM']"))
    if sources == ["nam_analysis"] and interval_seconds != 21600:
        findings.append(Finding("ERROR", "NAM-only source should use interval_seconds 21600"))
    if sources == ["rap_analysis"] and wps_fg_name != ["RAP"]:
        findings.append(Finding("ERROR", "RAP source should use wps_fg_name ['RAP']"))
    if sources == ["rap_analysis"] and interval_seconds != 3600:
        findings.append(Finding("ERROR", "RAP source should use interval_seconds 3600"))
    if sources == ["rap_analysis"]:
        if str(wps.get("ungrib_prefix", "")) != "RAP":
            findings.append(Finding("ERROR", "RAP source should use wps.ungrib_prefix RAP"))
        if [str(v) for v in as_list(wps.get("namelist_fg_name", wps_fg_name))] != ["RAP"]:
            findings.append(Finding("ERROR", "RAP source should use wps.namelist_fg_name ['RAP']"))
    # Single-stream HRRR is a PROVEN-BAD configuration for any run using a land
    # surface model, and the rules below used to enforce it. Public HRRR GRIB
    # (nat+sfc) contains ZERO soil-temperature messages and soil moisture only at
    # degenerate 0 / 0.01 m layers, so metgrid yields num_metgrid_soil_levels=0 and
    # real.exe cannot initialise Noah. Established by ashley2026_seiche gate C
    # (job 14135619 failed single-stream; 14136134 passed two-stream). RAP 130 was
    # confirmed to lack soil too; the working soil source is GFS 0.25 f000.
    if sources == ["hrrr"]:
        findings.append(
            Finding(
                "WARN",
                "single-stream HRRR has NO soil temperature (num_metgrid_soil_levels=0) "
                "and cannot initialise Noah -- use sources ['hrrr','gfs_soil'] with "
                "wps_fg_name ['HRRR','GFSSOIL'] unless this run has no land-surface model",
            )
        )
    if sources == ["hrrr"] and wps_fg_name != ["HRRR"]:
        findings.append(Finding("ERROR", "HRRR-only source should use wps_fg_name ['HRRR']"))
    if sources in (["hrrr"], ["hrrr", "gfs"], ["hrrr", "gfs_soil"]) and interval_seconds != 3600:
        findings.append(Finding("ERROR", "HRRR source should use interval_seconds 3600"))
    if sources == ["hrrr"]:
        if str(wps.get("ungrib_prefix", "")) != "HRRR":
            findings.append(Finding("ERROR", "HRRR source should use wps.ungrib_prefix HRRR"))
        if [str(v) for v in as_list(wps.get("namelist_fg_name", wps_fg_name))] != ["HRRR"]:
            findings.append(Finding("ERROR", "HRRR-only source should use wps.namelist_fg_name ['HRRR']"))
    if sources in (["hrrr", "gfs"], ["hrrr", "gfs_soil"]) and wps_fg_name != ["HRRR", "GFSSOIL"]:
        # ORDER, not just membership. metgrid reads fg_name by priority, so
        # ['GFSSOIL','HRRR'] would hand GFS the atmosphere and nothing would say so.
        findings.append(
            Finding(
                "ERROR",
                f"two-stream HRRR+soil must use wps_fg_name ['HRRR','GFSSOIL'] in that "
                f"order, got {wps_fg_name!r} -- metgrid reads fg_name by priority, so an "
                "inverted order silently gives GFS the atmosphere",
            )
        )

    # Two-stream HRRR atmosphere + GFS soil: the configuration that actually works.
    # metgrid takes fg_name in priority order, so HRRR must come FIRST (it wins
    # atmosphere and surface) and GFSSOIL second (it contributes only soil).
    if sources == ["hrrr", "gfs"]:
        if wps_fg_name != ["HRRR", "GFSSOIL"]:
            findings.append(Finding(
                "ERROR",
                "HRRR+GFS two-stream should use wps_fg_name ['HRRR','GFSSOIL'] in that "
                "order -- HRRR first so it wins atmosphere/surface, GFS adds only soil",
            ))
        if [str(v) for v in as_list(wps.get("namelist_fg_name", wps_fg_name))] != ["HRRR", "GFSSOIL"]:
            findings.append(Finding(
                "ERROR",
                "HRRR+GFS two-stream should use wps.namelist_fg_name ['HRRR','GFSSOIL']",
            ))
        # The HRRR stream must use a soil-stripped Vtable, or HRRR's degenerate soil
        # layers win over GFS's real ones and the run is back to the broken state.
        if str(wps.get("vtable", "")) != "Vtable.raphrrr.nosoil":
            findings.append(Finding(
                "ERROR",
                "HRRR+GFS two-stream needs wps.vtable 'Vtable.raphrrr.nosoil' (soil lines "
                "stripped) so GFS supplies soil; plain Vtable.raphrrr reinstates HRRR's "
                "degenerate 0/0.01 m layers",
            ))
        if str(wps.get("vtable", "")) != "Vtable.raphrrr":
            findings.append(
                Finding("WARN", "HRRR normally ungribs with John's Vtable.raphrrr")
            )
    if "gefs_reforecast" in sources and interval_seconds != 10800:
        findings.append(Finding("WARN", "GEFS reforecast stream normally uses 10800 seconds"))
    if "gefs_reforecast" in sources and wps_fg_name != ["GEFS", "NAM"]:
        findings.append(Finding("WARN", "two-stream GEFS+NAM should use fg_name ['GEFS', 'NAM']"))

    add_path_finding(
        findings, as_path(paths["wrf_src"]), "paths.wrf_src",
        strict_files=True, must_be_dir=True,
    )
    add_wrf_build_findings(
        findings,
        as_path(paths["wrf_build"]),
        strict_files=strict_files,
    )
    add_wps_root_findings(
        findings,
        as_path(paths["wps_root"]),
        strict_files=strict_files,
        vtable=str(data.get("wps", {}).get("vtable", "Vtable.NAM")),
        vtable_dir=(as_path(data["wps"]["vtable_dir"])
                    if data.get("wps", {}).get("vtable_dir") else None),
    )
    add_path_finding(
        findings, as_path(paths["geog_data_path"]), "paths.geog_data_path",
        strict_files=strict_files, must_be_dir=True,
    )
    for key in ("input_root", "run_root", "wps_run", "wrf_run", "archive_root"):
        add_path_finding(
            findings, as_path(paths[key]), f"paths.{key}",
            strict_files=strict_files, must_be_dir=True,
        )
    if "grib_data" in paths:
        add_path_finding(
            findings, as_path(paths["grib_data"]), "paths.grib_data",
            strict_files=strict_files, must_be_dir=True,
        )
    add_storage_policy_findings(findings, data, strict_files=strict_files)

    validate_manifest(
        findings,
        as_path(forcing["manifest_path"]),
        artifact_case_name,
        sources,
        strict_files,
    )
    validate_contract(
        findings,
        as_path(forcing["contract_path"]),
        artifact_case_name,
        wps_fg_name,
        interval_seconds,
        strict_files,
    )
    validate_namelists(findings, data, strict_files=strict_files)

    wrf_run = as_path(paths["wrf_run"])
    stale_met_em = []
    for item in sorted(glob.glob(str(wrf_run / "met_em.d0*.nc"))):
        path = Path(item)
        if path.is_symlink():
            try:
                if path.resolve().parent == as_path(paths["wps_run"]).resolve():
                    continue
            except OSError:
                pass
        stale_met_em.append(item)
    if stale_met_em:
        severity = "ERROR" if strict_files else "WARN"
        findings.append(
            Finding(severity, f"wrf_run contains stale met_em files: {len(stale_met_em)}")
        )

    wps_run = as_path(paths["wps_run"])
    met_em = sorted(glob.glob(str(wps_run / "met_em.d0*.nc")))
    expected_met_em_raw = forcing.get("expected_met_em_count")
    expected_met_em = None
    if expected_met_em_raw is not None:
        expected_met_em = parse_positive_int_setting(
            expected_met_em_raw,
            "forcing.expected_met_em_count",
            findings,
            allow_pending=True,
            strict_pending=False,
        )
    if met_em and expected_met_em is not None and len(met_em) != expected_met_em:
        findings.append(
            Finding(
                "WARN",
                f"wps_run has {len(met_em)} met_em files, expected {expected_met_em}",
            )
        )

    if int(slurm["nodes"]) != 1:
        findings.append(Finding("WARN", "validated Basin proof uses one Slurm node"))
    if int(slurm["ntasks"]) <= 0:
        findings.append(Finding("ERROR", "slurm.ntasks must be positive"))
    if str(slurm["account"]) != "lawson-np" or str(slurm["partition"]) != "lawson-np":
        findings.append(Finding("WARN", "default validated target is lawson-np"))
    if "srun --mpi=pmi2" not in str(slurm["mpi_launcher"]):
        findings.append(Finding("ERROR", "slurm.mpi_launcher must include 'srun --mpi=pmi2'"))
    if slurm.get("profile") == "owned_notch392_max":
        if str(slurm["account"]) != "lawson-np" or str(slurm["partition"]) != "lawson-np":
            findings.append(Finding("ERROR", "owned_notch392_max requires lawson-np account/partition"))
        if str(slurm.get("nodelist")) != "notch392":
            findings.append(Finding("ERROR", "owned_notch392_max requires nodelist notch392"))
        if int(slurm["nodes"]) != 1 or int(slurm["ntasks"]) != 56:
            findings.append(Finding("ERROR", "owned_notch392_max requires nodes=1 and ntasks=56"))
        memory_gib = parse_memory_gib(slurm["memory"])
        if memory_gib is None:
            findings.append(Finding("ERROR", f"could not parse slurm.memory: {slurm['memory']}"))
        elif memory_gib < 900:
            findings.append(Finding("WARN", "owned_notch392_max should request at least 900G"))

    archive = data.get("archive", {})
    if archive.get("colon_safe_wrfout_source") != "./wrfout_d0*":
        findings.append(Finding("WARN", "archive should use ./wrfout_d0* for colon-safe rsync"))

    return findings


def shell_quote(value: Any) -> str:
    return shlex.quote(str(value))


def text_value(value: Any) -> str:
    values = as_list(value)
    if not values:
        return ""
    return ", ".join(str(v) for v in values)


def expected_met_em_count_from_case(data: dict[str, Any]) -> int | None:
    findings: list[Finding] = []
    start = parse_case_datetime(data["case"]["start"], "start", findings)
    end = parse_case_datetime(data["case"]["end"], "end", findings)
    if findings or start is None or end is None:
        return None
    interval = int(data["forcing"]["interval_seconds"])
    domains = int(data["case"]["domains"])
    elapsed = int((end - start).total_seconds())
    if interval <= 0 or elapsed < 0 or elapsed % interval != 0:
        return None
    return domains * (elapsed // interval + 1)


def run_readiness_findings(data: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    forcing = data["forcing"]
    parse_positive_int_setting(
        forcing["num_metgrid_levels"],
        "forcing.num_metgrid_levels",
        findings,
        allow_pending=False,
    )
    if forcing.get("expected_met_em_count") is not None:
        parse_positive_int_setting(
            forcing["expected_met_em_count"],
            "forcing.expected_met_em_count",
            findings,
            allow_pending=False,
        )
    return findings


def add_wps_field_proof_findings(findings: list[Finding], data: dict[str, Any]) -> None:
    wps = data.get("wps", {})
    required = ("vtable", "ungrib_prefix", "namelist_fg_name", "namelist_template", "geogrid_source")
    for key in required:
        if key not in wps:
            findings.append(Finding("ERROR", f"wps.{key} is required for WPS field proof rendering"))

    if findings and any(f.severity == "ERROR" for f in findings):
        return

    if "/" in str(wps["vtable"]):
        findings.append(Finding("ERROR", f"wps.vtable must be a simple table name: {wps['vtable']!r}"))

    # TWO-STREAM. Public HRRR GRIB carries no soil temperature at all, so an
    # HRRR-forced run with a land-surface model MUST ungrib a second source for soil
    # and hand metgrid both via fg_name. That is now the standard shape for every
    # HRRR case here, not an exotic one, so the proof renderer has to express it.
    #
    # fg_name is read by metgrid IN PRIORITY ORDER, so the atmosphere stream has to
    # come first: inverted, GFS would take the atmosphere away from HRRR and nothing
    # would complain. That ordering is the rule enforced below.
    fg_names = [str(v) for v in as_list(wps["namelist_fg_name"])]
    extra = as_list(wps.get("extra_streams", []))
    extra_prefixes = [str(s.get("prefix", "")) for s in extra if isinstance(s, dict)]

    if not fg_names:
        findings.append(Finding("ERROR", "wps.namelist_fg_name is empty"))
    elif str(wps["ungrib_prefix"]) != fg_names[0]:
        findings.append(
            Finding(
                "ERROR",
                f"wps.ungrib_prefix {wps['ungrib_prefix']!r} must be the FIRST entry of "
                f"wps.namelist_fg_name {fg_names!r} -- metgrid reads fg_name by priority, "
                "so the atmosphere stream has to win",
            )
        )
    for name in fg_names[1:]:
        if name not in extra_prefixes:
            findings.append(
                Finding(
                    "ERROR",
                    f"wps.namelist_fg_name lists {name!r} but no wps.extra_streams entry "
                    f"declares that prefix (declared: {extra_prefixes or 'none'})",
                )
            )
    for index, stream in enumerate(extra):
        if not isinstance(stream, dict):
            findings.append(Finding("ERROR", f"wps.extra_streams[{index}] must be a mapping"))
            continue
        for key in ("prefix", "vtable", "source"):
            if not stream.get(key):
                findings.append(
                    Finding("ERROR", f"wps.extra_streams[{index}] missing '{key}'")
                )
        if stream.get("vtable") and "/" in str(stream["vtable"]):
            findings.append(
                Finding("ERROR", f"wps.extra_streams[{index}].vtable must be a simple table name")
            )
        if str(stream.get("prefix", "")) not in fg_names:
            findings.append(
                Finding(
                    "WARN",
                    f"wps.extra_streams[{index}].prefix {stream.get('prefix')!r} is not in "
                    "wps.namelist_fg_name, so metgrid would never read it",
                )
            )
    for key in ("namelist_template", "geogrid_source"):
        add_path_finding(
            findings,
            as_path(wps[key]),
            f"wps.{key}",
            strict_files=False,
            must_be_dir=(key == "geogrid_source"),
        )


def render_slurm(data: dict[str, Any], case_file: Path) -> str:
    case = data["case"]
    forcing = data["forcing"]
    paths = data["paths"]
    wps = data.get("wps", {})
    slurm = data["slurm"]

    job_name = str(slurm["job_name"])
    archive_root = as_path(paths["archive_root"])
    wrf_run = as_path(paths["wrf_run"])
    wrf_build = as_path(paths["wrf_build"])
    wrf_src = as_path(paths["wrf_src"])
    expected_real = wrf_build / "main" / "real.exe"
    expected_wrf = wrf_build / "main" / "wrf.exe"
    mpi_launcher = str(slurm["mpi_launcher"])
    slurm_chdir = slurm.get("chdir")
    slurm_output = slurm.get("output")
    if not slurm_chdir:
        slurm_chdir = PRACTICAL_SLURM_LOG_ROOT
    if not slurm_output:
        slurm_output = PRACTICAL_SLURM_LOG_ROOT / f"{safe_name(job_name)}_%j.out"
    if slurm.get("profile") == "gate11_practical_review":
        if not slurm_chdir:
            slurm_chdir = PRACTICAL_SLURM_LOG_ROOT
        if not slurm_output:
            slurm_output = PRACTICAL_SLURM_LOG_ROOT / f"{safe_name(job_name)}_%j.out"
    wps_prefix = wps.get("ungrib_prefix", "unset")
    namelist_fg_name = text_value(wps.get("namelist_fg_name", forcing["wps_fg_name"]))

    lines = [
        "#!/bin/bash",
        f"# Rendered by brc-cases/wrf_case.py from {case_file}",
        "# Review only. Do not submit without explicit human approval.",
        f"#SBATCH --job-name={job_name}",
        f"#SBATCH --account={slurm['account']}",
        f"#SBATCH --partition={slurm['partition']}",
        f"#SBATCH --nodes={slurm['nodes']}",
        f"#SBATCH --ntasks={slurm['ntasks']}",
        f"#SBATCH --mem={slurm['memory']}",
        f"#SBATCH --time={slurm['time']}",
    ]
    if slurm.get("nodelist"):
        lines.append(f"#SBATCH --nodelist={slurm['nodelist']}")
    if slurm_chdir:
        lines.append(f"#SBATCH --chdir={slurm_chdir}")
    if slurm_output:
        lines.append(f"#SBATCH --output={slurm_output}")
        lines.append(f"#SBATCH --error={slurm_output}")
    lines.extend(
        [
            "",
            "set -euo pipefail",
            "",
            f"CASE_NAME={shell_quote(case['name'])}",
            f"WRF_SRC={shell_quote(wrf_src)}",
            f"WRF_BUILD={shell_quote(wrf_build)}",
            f"WRF_RUN={shell_quote(wrf_run)}",
            f"ARCHIVE_ROOT={shell_quote(archive_root)}",
            f"EXPECTED_REAL={shell_quote(expected_real)}",
            f"EXPECTED_WRF={shell_quote(expected_wrf)}",
            'ARCHIVE_DIR="${ARCHIVE_ROOT}/run_$(date -u +%Y%m%dT%H%M%SZ)"',
            'DEBUG_DIR="${WRF_RUN}/brc_run_debug"',
            'SUMMARY_LOG="${DEBUG_DIR}/run_debug_summary.txt"',
            'PHASE_LOG="${DEBUG_DIR}/run_phase_times.tsv"',
            'INVENTORY_LOG="${DEBUG_DIR}/run_file_inventory.tsv"',
            "",
            'utc_now() { date -u +%Y-%m-%dT%H:%M:%SZ; }',
            'epoch_now() { date -u +%s; }',
            'fail() { printf "ERROR: %s\\n" "$*" >&2; exit 2; }',
            'require_file() { [[ -f "$1" ]] || fail "missing required file: $1"; }',
            'require_executable() { [[ -x "$1" ]] || fail "missing required executable: $1"; }',
            'require_glob() { compgen -G "$1" >/dev/null || fail "missing required files matching: $1"; }',
            "preflight_missing=0",
            'check_dir() { [[ -d "$1" ]] || { printf "ERROR: missing required directory: %s\\n" "$1" >&2; preflight_missing=1; }; }',
            'check_file() { [[ -f "$1" ]] || { printf "ERROR: missing required file: %s\\n" "$1" >&2; preflight_missing=1; }; }',
            'check_executable() { [[ -x "$1" ]] || { printf "ERROR: missing required executable: %s\\n" "$1" >&2; preflight_missing=1; }; }',
            'check_glob() { compgen -G "$1" >/dev/null || { printf "ERROR: missing required files matching: %s\\n" "$1" >&2; preflight_missing=1; }; }',
            "require_matching_executable() {",
            "  local expected=\"$1\" actual=\"$2\" label=\"$3\"",
            "  local expected_resolved actual_resolved",
            "  require_executable \"$expected\"",
            "  require_executable \"$actual\"",
            "  expected_resolved=$(readlink -f \"$expected\" 2>/dev/null || printf unresolved)",
            "  actual_resolved=$(readlink -f \"$actual\" 2>/dev/null || printf unresolved)",
            "  if ! cmp -s \"$expected\" \"$actual\"; then",
            "    {",
            "      printf \"executable_provenance_%s\\tFAIL\\n\" \"$label\"",
            "      printf \"expected_%s\\t%s\\n\" \"$label\" \"$expected_resolved\"",
            "      printf \"actual_%s\\t%s\\n\" \"$label\" \"$actual_resolved\"",
            "    } >> \"$SUMMARY_LOG\"",
            "    fail \"$label does not match John-owned WRF build; expected $expected_resolved, actual $actual_resolved\"",
            "  fi",
            "  {",
            "    printf \"executable_provenance_%s\\tPASS\\n\" \"$label\"",
            "    printf \"expected_%s\\t%s\\n\" \"$label\" \"$expected_resolved\"",
            "    printf \"actual_%s\\t%s\\n\" \"$label\" \"$actual_resolved\"",
            "  } >> \"$SUMMARY_LOG\"",
            "}",
            "require_matching_file() {",
            "  local expected=\"$1\" actual=\"$2\" label=\"$3\"",
            "  local expected_resolved actual_resolved",
            "  require_file \"$expected\"",
            "  require_file \"$actual\"",
            "  expected_resolved=$(readlink -f \"$expected\" 2>/dev/null || printf unresolved)",
            "  actual_resolved=$(readlink -f \"$actual\" 2>/dev/null || printf unresolved)",
            "  if ! cmp -s \"$expected\" \"$actual\"; then",
            "    {",
            "      printf \"runtime_file_%s\\tFAIL\\n\" \"$label\"",
            "      printf \"expected_runtime_%s\\t%s\\n\" \"$label\" \"$expected_resolved\"",
            "      printf \"actual_runtime_%s\\t%s\\n\" \"$label\" \"$actual_resolved\"",
            "    } >> \"$SUMMARY_LOG\"",
            "    fail \"runtime file $label does not match John-owned WRF run directory; expected $expected_resolved, actual $actual_resolved\"",
            "  fi",
            "  {",
            "    printf \"runtime_file_%s\\tPASS\\n\" \"$label\"",
            "    printf \"expected_runtime_%s\\t%s\\n\" \"$label\" \"$expected_resolved\"",
            "    printf \"actual_runtime_%s\\t%s\\n\" \"$label\" \"$actual_resolved\"",
            "  } >> \"$SUMMARY_LOG\"",
            "}",
            "",
            "run_phase() {",
            "  local phase=\"$1\"",
            "  shift",
            "  local start_utc start_epoch end_utc end_epoch rc",
            "  start_utc=$(utc_now)",
            "  start_epoch=$(epoch_now)",
            "  set +e",
            "  \"$@\"",
            "  rc=$?",
            "  set -e",
            "  end_utc=$(utc_now)",
            "  end_epoch=$(epoch_now)",
            "  printf \"%s\\t%s\\t%s\\t%s\\t%s\\n\" \\",
            "    \"$phase\" \"$start_utc\" \"$end_utc\" \"$((end_epoch - start_epoch))\" \"$rc\" >> \"$PHASE_LOG\"",
            "  return \"$rc\"",
            "}",
            "",
            "write_inventory() {",
            "  local pattern count bytes newest",
            "  {",
            "    printf \"pattern\\tcount\\tbytes\\tnewest_epoch\\n\"",
            "    for pattern in met_em.d0*.nc wrfinput_d0* wrfbdy_d01 wrfout_d0* rsl.out.* rsl.error.* real.rsl.out.* real.rsl.error.*; do",
            "      count=$(find . -maxdepth 1 -name \"$pattern\" -type f | wc -l)",
            "      bytes=$(find . -maxdepth 1 -name \"$pattern\" -type f -printf '%s\\n' | awk '{s+=$1} END{print s+0}')",
            "      newest=$(find . -maxdepth 1 -name \"$pattern\" -type f -printf '%T@\\n' | sort -nr | head -n 1)",
            "      newest=${newest:-NA}",
            "      printf \"%s\\t%s\\t%s\\t%s\\n\" \"$pattern\" \"$count\" \"$bytes\" \"$newest\"",
            "    done",
            "  } > \"$INVENTORY_LOG\"",
            "}",
            "",
            "write_summary_preamble() {",
            "  {",
            "    printf \"BRC WRF run debug summary\\n\"",
            "    printf \"generated_utc\\t%s\\n\" \"$(utc_now)\"",
            "    printf \"case\\t%s\\n\" \"$CASE_NAME\"",
            "    printf \"job_id\\t%s\\n\" \"${SLURM_JOB_ID:-none}\"",
            "    printf \"host\\t%s\\n\" \"$(hostname)\"",
            "    printf \"submit_dir\\t%s\\n\" \"${SLURM_SUBMIT_DIR:-unset}\"",
            "    printf \"wrf_src\\t%s\\n\" \"$WRF_SRC\"",
            "    printf \"wrf_build\\t%s\\n\" \"$WRF_BUILD\"",
            "    printf \"wrf_run\\t%s\\n\" \"$WRF_RUN\"",
            "    printf \"archive_dir\\t%s\\n\" \"$ARCHIVE_DIR\"",
            "    printf \"wrf_commit\\t%s\\n\" \"$(git -C \"$WRF_SRC\" rev-parse --short HEAD 2>/dev/null || printf unknown)\"",
            "    printf \"expected_real\\t%s\\n\" \"$EXPECTED_REAL\"",
            "    printf \"expected_wrf\\t%s\\n\" \"$EXPECTED_WRF\"",
            "    printf \"resolved_real\\t%s\\n\" \"$(readlink -f \"$WRF_RUN/real.exe\" 2>/dev/null || printf unresolved)\"",
            "    printf \"resolved_wrf\\t%s\\n\" \"$(readlink -f \"$WRF_RUN/wrf.exe\" 2>/dev/null || printf unresolved)\"",
            f"    printf \"manifest_path\\t%s\\n\" {shell_quote(forcing['manifest_path'])}",
            f"    printf \"contract_path\\t%s\\n\" {shell_quote(forcing['contract_path'])}",
            "    printf \"\\nSettings\\n\"",
            "    printf \"| Item | Value |\\n\"",
            "    printf \"| --- | --- |\\n\"",
            f"    printf \"| Case window | %s to %s |\\n\" {shell_quote(case['start'])} {shell_quote(case['end'])}",
            f"    printf \"| Domains | %s |\\n\" {shell_quote(case['domains'])}",
            f"    printf \"| Forcing | %s |\\n\" {shell_quote(text_value(forcing['sources']))}",
            f"    printf \"| WPS cadence | interval_seconds = %s |\\n\" {shell_quote(forcing['interval_seconds'])}",
            f"    printf \"| WPS Vtable | %s |\\n\" {shell_quote(wps.get('vtable', 'unset'))}",
            f"    printf \"| WPS prefix / fg_name | %s / %s |\\n\" {shell_quote(wps_prefix)} {shell_quote(namelist_fg_name)}",
            f"    printf \"| met_em count / levels | %s files / %s levels |\\n\" {shell_quote(forcing.get('expected_met_em_count', 'unset'))} {shell_quote(forcing['num_metgrid_levels'])}",
            f"    printf \"| Slurm shape | %s node(s), %s task(s), %s, %s |\\n\" {shell_quote(slurm['nodes'])} {shell_quote(slurm['ntasks'])} {shell_quote(slurm['memory'])} {shell_quote(slurm['time'])}",
            f"    printf \"| Launcher | %s |\\n\" {shell_quote(mpi_launcher)}",
            "    printf \"\\nGotchas\\n\"",
            "    printf \"1. Do not run practical checks from login nodes; this script belongs in approved Slurm/compute context.\\n\"",
            "    printf \"2. Keep ungrib prefix and metgrid fg_name paired.\\n\"",
            "    printf \"3. Use the case contract cadence; NAM proof is 21600 seconds, RAP is 3600 seconds, and GEFS+NAM would be separate.\\n\"",
            "    printf \"4. Use srun --mpi=pmi2 for wrf.exe on this Intel MPI stack.\\n\"",
            "    printf \"5. Check real.exe, wrf.exe, archive completeness, and Slurm state as separate facts.\\n\"",
            "    printf \"\\nModules\\n\"",
            "    module -t list 2>&1 || true",
            "  } > \"$SUMMARY_LOG\"",
            "}",
            "",
            "finalize_debug() {",
            "  local rc=$?",
            "  set +e",
            "  printf \"final_status\\t%s\\n\" \"$rc\" >> \"$SUMMARY_LOG\"",
            "  printf \"finished_utc\\t%s\\n\" \"$(utc_now)\" >> \"$SUMMARY_LOG\"",
            "  write_inventory",
            "  mkdir -p \"$ARCHIVE_DIR/debug\"",
            "  rsync -av \"$DEBUG_DIR\"/ \"$ARCHIVE_DIR/debug/\" >/dev/null 2>&1",
            "  exit \"$rc\"",
            "}",
            "",
            'check_dir "$WRF_RUN"',
            'check_executable "$WRF_RUN/real.exe"',
            'check_executable "$WRF_RUN/wrf.exe"',
            'check_file "$WRF_RUN/namelist.input"',
            'check_glob "$WRF_RUN/met_em.d0*.nc"',
            f"for runtime_file in {' '.join(REQUIRED_WRF_RUNTIME_FILES)}; do",
            '  check_file "$WRF_BUILD/run/$runtime_file"',
            '  check_file "$WRF_RUN/$runtime_file"',
            "done",
            '(( preflight_missing == 0 )) || fail "preflight failed; prepare WRF_RUN before resubmitting"',
            "",
            'mkdir -p "$DEBUG_DIR"',
            'cd "$WRF_RUN"',
            "printf \"phase\\tstart_utc\\tend_utc\\telapsed_seconds\\texit_code\\n\" > \"$PHASE_LOG\"",
            "trap finalize_debug EXIT",
            "",
            "module purge",
            "module load intel-oneapi-compilers/2021.4.0",
            "module load intel-oneapi-mpi/2021.1.1",
            "module load hdf5/1.14.3",
            "module load netcdf-c/4.9.2",
            "module load netcdf-fortran/4.6.1",
            "",
            "export NETCDF=$(nf-config --prefix)",
            "export NETCDF_C=$(nc-config --prefix)",
            "export JASPERLIB=/usr/lib64",
            "export JASPERINC=/usr/include/jasper",
            "",
            "write_summary_preamble",
            'require_matching_executable "$EXPECTED_REAL" "$WRF_RUN/real.exe" "real.exe"',
            'require_matching_executable "$EXPECTED_WRF" "$WRF_RUN/wrf.exe" "wrf.exe"',
            f"for runtime_file in {' '.join(REQUIRED_WRF_RUNTIME_FILES)}; do",
            '  require_matching_file "$WRF_BUILD/run/$runtime_file" "$WRF_RUN/$runtime_file" "$runtime_file"',
            "done",
            "",
            "run_phase real.exe ./real.exe",
            'run_phase real_success_marker grep -q "SUCCESS COMPLETE REAL_EM INIT" rsl.out.0000',
            "mv rsl.out.0000 real.rsl.out.0000",
            "mv rsl.error.0000 real.rsl.error.0000",
            "write_inventory",
            "",
            f"run_phase wrf.exe {mpi_launcher} -n \"$SLURM_NTASKS\" ./wrf.exe",
            'run_phase wrf_success_marker grep -q "SUCCESS COMPLETE WRF" rsl.out.0000',
            "write_inventory",
            "",
            'mkdir -p "$ARCHIVE_DIR"',
            'run_phase archive_wrfout rsync -av ./wrfout_d0* "$ARCHIVE_DIR/"',
            "run_phase archive_logs rsync -av namelist.input rsl.out.0000 rsl.error.0000 \\",
            '  real.rsl.out.0000 real.rsl.error.0000 "$ARCHIVE_DIR/"',
            "",
            'printf "case=%s archive=%s\\n" "$CASE_NAME" "$ARCHIVE_DIR"',
        ]
    )
    return "\n".join(lines) + "\n"


def safe_name(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("_") or "item"


def render_wps_field_proof_slurm(data: dict[str, Any], case_file: Path) -> str:
    case = data["case"]
    forcing = data["forcing"]
    paths = data["paths"]
    wps = data.get("wps", {})
    slurm = data["slurm"]

    case_name = str(case["name"])
    job_name = f"wps_{safe_name(case_name)}"
    run_root = as_path(paths["run_root"])
    archive_root = as_path(paths["archive_root"])
    wps_root = as_path(paths["wps_root"])
    input_root = as_path(paths["input_root"])
    manifest_path = as_path(forcing["manifest_path"])
    contract_path = as_path(forcing["contract_path"])
    namelist_template = as_path(wps["namelist_template"])
    geogrid_source = as_path(wps["geogrid_source"])
    source_name = str(as_list(forcing["sources"])[0])
    grib_source = input_root / source_name
    expected_met_em = expected_met_em_count_from_case(data)
    expected_met_em_text = str(expected_met_em) if expected_met_em is not None else "unknown"
    # Fortran namelist list literal: 'HRRR','GFSSOIL'. text_value() would give
    # "HRRR, GFSSOIL", which becomes the single string 'HRRR, GFSSOIL' -- one stream
    # named after two, and metgrid would look for a prefix nothing wrote.
    fg_names = [str(v) for v in as_list(wps.get("namelist_fg_name", forcing["wps_fg_name"]))]
    fg_name_literal = ",".join(f"'{n}'" for n in fg_names)

    # Streams in fg_name priority order: the primary (atmosphere) first, then each
    # declared extra. Encoded as prefix|vtable|grib_dir|single so the rendered bash
    # can loop without needing a parser.
    extra_streams = [s for s in as_list(wps.get("extra_streams", [])) if isinstance(s, dict)]
    stream_specs = [
        "|".join([
            str(wps["ungrib_prefix"]),
            str(wps["vtable"]),
            str(input_root / source_name),
            "all",
        ])
    ]
    for stream in extra_streams:
        stream_specs.append(
            "|".join([
                str(stream["prefix"]),
                str(stream["vtable"]),
                str(stream.get("grib_dir") or (input_root / str(stream["source"]))),
                "single" if stream.get("single_time") else "all",
            ])
        )
    vtable_dir = wps.get("vtable_dir") or (wps_root / "ungrib" / "Variable_Tables")
    field_patterns = "\n".join(f"{name}\t{pattern}" for name, pattern in WPS_FIELD_CHECKS)

    lines = [
        "#!/bin/bash",
        f"# Rendered by brc-cases/wrf_case.py from {case_file}",
        "# WPS-only RAP field proof. Do not run real.exe, wrf.exe, quicklooks, or the full conveyor.",
        "# Submit only after explicit human approval for this WPS field-adequacy proof.",
        f"#SBATCH --job-name={job_name}",
        f"#SBATCH --account={slurm['account']}",
        f"#SBATCH --partition={slurm['partition']}",
        "#SBATCH --nodes=1",
        "#SBATCH --ntasks=8",
        "#SBATCH --mem=120G",
        "#SBATCH --time=01:30:00",
    ]
    if slurm.get("nodelist"):
        lines.append(f"#SBATCH --nodelist={slurm['nodelist']}")
    lines.extend(
        [
            f"#SBATCH --chdir={PRACTICAL_SLURM_LOG_ROOT}",
            f"#SBATCH --output={PRACTICAL_SLURM_LOG_ROOT}/{job_name}_%j.out",
            f"#SBATCH --error={PRACTICAL_SLURM_LOG_ROOT}/{job_name}_%j.out",
            "",
            "set -euo pipefail",
            "",
            'fail() { printf "ERROR: %s\\n" "$*" >&2; exit 2; }',
            '[[ "${BRC_WPS_FIELD_PROOF_APPROVED:-NO}" == "YES" ]] || fail "set BRC_WPS_FIELD_PROOF_APPROVED=YES only after explicit approval for this WPS-only proof"',
            "",
            f"CASE_NAME={shell_quote(case_name)}",
            f"CASE_FILE={shell_quote(case_file)}",
            f"CASE_START={shell_quote(case['start'])}",
            f"CASE_END={shell_quote(case['end'])}",
            f"DOMAINS={shell_quote(case['domains'])}",
            f"INTERVAL_SECONDS={shell_quote(forcing['interval_seconds'])}",
            f"EXPECTED_MET_EM_COUNT={shell_quote(expected_met_em_text)}",
            f"WPS_ROOT={shell_quote(wps_root)}",
            f"RUN_ROOT={shell_quote(run_root)}",
            f"ARCHIVE_ROOT={shell_quote(archive_root)}",
            f"INPUT_ROOT={shell_quote(input_root)}",
            f"GRIB_SOURCE={shell_quote(grib_source)}",
            f"MANIFEST={shell_quote(manifest_path)}",
            f"CONTRACT={shell_quote(contract_path)}",
            f"NAMELIST_TEMPLATE={shell_quote(namelist_template)}",
            f"GEOGRID_SOURCE={shell_quote(geogrid_source)}",
            f"VTABLE_NAME={shell_quote(wps['vtable'])}",
            f"UNGRIB_PREFIX={shell_quote(wps['ungrib_prefix'])}",
            f"METGRID_FG_NAME={shell_quote(fg_name_literal)}",
            f"PRIMARY_PREFIX={shell_quote(wps['ungrib_prefix'])}",
            f"VTABLE_DIR={shell_quote(vtable_dir)}",
            "STREAMS=(" + " ".join(shell_quote(s) for s in stream_specs) + ")",
            f"GEOG_DATA_PATH={shell_quote(paths['geog_data_path'])}",
            f"WRF_SRC={shell_quote(paths['wrf_src'])}",
            "export CASE_START CASE_END DOMAINS INTERVAL_SECONDS UNGRIB_PREFIX METGRID_FG_NAME GEOG_DATA_PATH NML_START NML_END",
            'RUN_ID="wps_field_proof_${SLURM_JOB_ID:-manual}_$(date -u +%Y%m%dT%H%M%SZ)"',
            'WPS_WORK="${RUN_ROOT}/${RUN_ID}/wps_run"',
            'GRIB_DATA="${RUN_ROOT}/${RUN_ID}/grib_data"',
            'ARCHIVE_DIR="${ARCHIVE_ROOT}/wps_field_proof/${RUN_ID}"',
            'DEBUG_DIR="${ARCHIVE_DIR}/debug"',
            "",
            'utc_now() { date -u +%Y-%m-%dT%H:%M:%SZ; }',
            "run_phase() {",
            "  local phase=\"$1\"",
            "  shift",
            "  local start end rc",
            "  start=$(date -u +%s)",
            "  set +e",
            "  \"$@\"",
            "  rc=$?",
            "  set -e",
            "  end=$(date -u +%s)",
            "  printf \"%s\\t%s\\t%s\\n\" \"$phase\" \"$((end - start))\" \"$rc\" >> \"$DEBUG_DIR/wps_phase_times.tsv\"",
            "  return \"$rc\"",
            "}",
            "",
            'case "$WPS_ROOT" in *"/u6060939/"*) fail "WPS_ROOT points into Michael-owned comparison path: $WPS_ROOT" ;; esac',
            '[[ "$WPS_WORK/" == "$RUN_ROOT/"* ]] || fail "WPS_WORK is outside RUN_ROOT: $WPS_WORK"',
            '[[ "$ARCHIVE_DIR/" == "$ARCHIVE_ROOT/"* ]] || fail "ARCHIVE_DIR is outside ARCHIVE_ROOT: $ARCHIVE_DIR"',
            'test -x "$WPS_ROOT/ungrib.exe"',
            'test -x "$WPS_ROOT/metgrid.exe"',
            'test -f "$WPS_ROOT/link_grib.csh"',
            # Resolve the primary Vtable the SAME WAY the ungrib loop below does:
            # vtable_dir first, then the WPS tree. This used to test the WPS tree
            # unconditionally, which is a location the script never actually reads --
            # every stream, including the primary one, is linked from "$VTABLE_DIR/..."
            # in the STREAMS loop. A case whose Vtables live in its own control packet
            # (the two-stream HRRR+GFS-soil design: Vtable.raphrrr.nosoil and
            # Vtable.gfssoil ship in neither WPS nor this repo) therefore aborted at a
            # precondition that contradicted the execution path.
            'test -f "$VTABLE_DIR/$VTABLE_NAME" '
            '|| test -f "$WPS_ROOT/ungrib/Variable_Tables/$VTABLE_NAME" '
            '|| fail "Vtable $VTABLE_NAME is in neither $VTABLE_DIR nor $WPS_ROOT/ungrib/Variable_Tables"',
            'test -f "$NAMELIST_TEMPLATE"',
            'test -d "$GEOGRID_SOURCE"',
            'compgen -G "$GEOGRID_SOURCE/geo_em.d0*.nc" >/dev/null || fail "missing geo_em.d0*.nc in GEOGRID_SOURCE=$GEOGRID_SOURCE"',
            'test -d "$GRIB_SOURCE"',
            'test -f "$MANIFEST"',
            'test -f "$CONTRACT"',
            "",
            'mkdir -p "$WPS_WORK" "$GRIB_DATA" "$DEBUG_DIR"',
            'printf "phase\\telapsed_seconds\\texit_code\\n" > "$DEBUG_DIR/wps_phase_times.tsv"',
            'find "$GRIB_SOURCE" -maxdepth 1 -type f \\( -name "*.grb" -o -name "*.grb2" -o -name "*.grib" -o -name "*.grib2" \\) | sort > "$DEBUG_DIR/grib_files.txt"',
            'grib_count=$(wc -l < "$DEBUG_DIR/grib_files.txt")',
            '[[ "$grib_count" -gt 0 ]] || fail "no GRIB files found under $GRIB_SOURCE"',
            'mapfile -t GRIB_FILES < "$DEBUG_DIR/grib_files.txt"',
            "",
            "module purge",
            "module load intel-oneapi-compilers/2021.4.0",
            "module load intel-oneapi-mpi/2021.1.1",
            "module load hdf5/1.14.3",
            "module load netcdf-c/4.9.2",
            "module load netcdf-fortran/4.6.1",
            "export NETCDF=$(nf-config --prefix)",
            "export NETCDF_C=$(nc-config --prefix)",
            "export JASPERLIB=/usr/lib64",
            "export JASPERINC=/usr/include/jasper",
            "",
            'cd "$WPS_WORK"',
            'ln -sfn "$WPS_ROOT/ungrib" ungrib',
            'ln -sfn "$WPS_ROOT/metgrid" metgrid',
            'ln -sf "$WPS_ROOT/ungrib.exe" ungrib.exe',
            'ln -sf "$WPS_ROOT/metgrid.exe" metgrid.exe',
            'ln -sf "$WPS_ROOT/link_grib.csh" link_grib.csh',
            'rsync -av "$GEOGRID_SOURCE"/geo_em.d0*.nc "$WPS_WORK"/',
            "",
            "# The valid times metgrid will be asked for. A single-time stream (soil,",
            "# typically) has its one intermediate duplicated across all of them.",
            'mapfile -t TIMES < <(python3 -c "',
            "import datetime, os, sys",
            "fmt = \\\"%Y-%m-%d_%H:%M:%S\\\"",
            "start = datetime.datetime.strptime(os.environ[\\\"CASE_START\\\"], fmt)",
            "end = datetime.datetime.strptime(os.environ[\\\"CASE_END\\\"], fmt)",
            "step = datetime.timedelta(seconds=int(os.environ[\\\"INTERVAL_SECONDS\\\"]))",
            "t = start",
            "while t <= end:",
            "    print(t.strftime(\\\"%Y-%m-%d_%H\\\"))",
            "    t += step",
            '")',
            'echo "metgrid valid times: ${TIMES[*]}"',
            "",
            "# Rewrite namelist.wps for the current stream. Called once per ungrib pass",
            "# with UNGRIB_PREFIX set, then once more before metgrid. Only the dates,",
            "# prefix and fg_name are touched -- &geogrid comes from the template, which",
            "# domain_calc.py derived from the spec, so the proof cannot drift from it.",
            "emit_namelist() {",
            'python3 - "$NAMELIST_TEMPLATE" "$WPS_WORK/namelist.wps" <<\'PY\'',
            "import os",
            "import re",
            "import sys",
            "",
            "template, output = sys.argv[1:]",
            "domains = int(os.environ['DOMAINS'])",
            "# NML_START/NML_END let a single-time stream (soil) ungrib over just its",
            "# one valid time. Asking ungrib for seven times it has one GRIB for is how",
            "# a two-stream proof fails confusingly.",
            "start = os.environ.get('NML_START') or os.environ['CASE_START']",
            "end = os.environ.get('NML_END') or os.environ['CASE_END']",
            "interval = os.environ['INTERVAL_SECONDS']",
            "prefix = os.environ['UNGRIB_PREFIX']",
            "fg_name = os.environ['METGRID_FG_NAME']",
            "geog = os.environ['GEOG_DATA_PATH'].rstrip('/') + '/'",
            "",
            "def repeated(value: str) -> str:",
            "    return ','.join(f\"'{value}'\" for _ in range(domains))",
            "",
            "text = open(template, encoding='utf-8').read()",
            "replacements = {",
            "    r'(?m)^\\s*start_date\\s*=.*$': f\" start_date = {repeated(start)},\",",
            "    r'(?m)^\\s*end_date\\s*=.*$': f\" end_date   = {repeated(end)},\",",
            "    r'(?m)^\\s*interval_seconds\\s*=.*$': f\" interval_seconds = {interval}\",",
            "    r'(?m)^\\s*geog_data_path\\s*=.*$': f\" geog_data_path = '{geog}'\",",
            "    r'(?m)^\\s*prefix\\s*=.*$': f\" prefix = '{prefix}',\",",
            "    r'(?m)^\\s*fg_name\\s*=.*$': f\" fg_name = {fg_name}\",",
            "}",
            "for pattern, replacement in replacements.items():",
            "    text, count = re.subn(pattern, replacement, text)",
            "    if count != 1:",
            "        raise SystemExit(f'expected one namelist replacement for {pattern}, got {count}')",
            "open(output, 'w', encoding='utf-8').write(text)",
            "PY",
            "}",
            "",
            "# ---- ungrib, once per stream, in fg_name priority order ----",
            "for spec in \"${STREAMS[@]}\"; do",
            '  IFS="|" read -r s_prefix s_vtable s_gribdir s_single <<< "$spec"',
            '  echo "=== ungrib stream $s_prefix (Vtable $s_vtable, single_time=$s_single) ==="',
            '  vt="$VTABLE_DIR/$s_vtable"',
            '  test -f "$vt" || vt="$WPS_ROOT/ungrib/Variable_Tables/$s_vtable"',
            '  test -f "$vt" || fail "Vtable not found for stream $s_prefix: $s_vtable"',
            '  rm -f GRIBFILE.*',
            '  ln -sf "$vt" Vtable',
            '  if [[ "$s_single" == "single" ]]; then',
            '    UNGRIB_PREFIX="$s_prefix" NML_START="$CASE_START" NML_END="$CASE_START" emit_namelist',
            "  else",
            '    UNGRIB_PREFIX="$s_prefix" emit_namelist',
            "  fi",
            '  mapfile -t s_files < <(find "$s_gribdir" -maxdepth 1 -type f \\( -name "*.grb" -o -name "*.grb2" -o -name "*.grib" -o -name "*.grib2" \\) | sort)',
            '  [[ "${#s_files[@]}" -gt 0 ]] || fail "no GRIB under $s_gribdir for stream $s_prefix"',
            '  "$WPS_ROOT/link_grib.csh" "${s_files[@]}"',
            '  run_phase "ungrib_${s_prefix}" ./ungrib.exe',
            '  mv -f ungrib.log "$DEBUG_DIR/ungrib_${s_prefix}.log" 2>/dev/null || true',
            '  compgen -G "${s_prefix}:*" >/dev/null || fail "stream $s_prefix produced no intermediate"',
            '  if [[ "$s_single" == "single" ]]; then',
            '    src=$(ls -1 "${s_prefix}":* | head -1)',
            '    for t in "${TIMES[@]}"; do',
            '      [[ -f "${s_prefix}:${t}" ]] || cp -f "$src" "${s_prefix}:${t}"',
            "    done",
            '    echo "  duplicated $(basename "$src") across ${#TIMES[@]} valid times"',
            "  fi",
            "  for t in \"${TIMES[@]}\"; do",
            '    test -f "${s_prefix}:${t}" || fail "stream $s_prefix has no intermediate at $t"',
            "  done",
            "done",
            "",
            "# ---- metgrid, reading every stream in fg_name order ----",
            'UNGRIB_PREFIX="$PRIMARY_PREFIX" emit_namelist',
            'cp "$WPS_WORK/namelist.wps" "$DEBUG_DIR/namelist.wps.metgrid"',
            "run_phase metgrid ./metgrid.exe",
            "",
            'find "$WPS_WORK" -maxdepth 1 -type f -name "met_em.d0*.nc" | sort > "$DEBUG_DIR/met_em_files.txt"',
            'met_count=$(wc -l < "$DEBUG_DIR/met_em_files.txt")',
            'if [[ "$EXPECTED_MET_EM_COUNT" != "unknown" && "$met_count" -ne "$EXPECTED_MET_EM_COUNT" ]]; then',
            '  fail "expected $EXPECTED_MET_EM_COUNT met_em files, found $met_count"',
            "fi",
            'sample_met=$(head -n 1 "$DEBUG_DIR/met_em_files.txt")',
            '[[ -n "$sample_met" ]] || fail "metgrid produced no met_em files"',
            'command -v ncdump >/dev/null || fail "ncdump is unavailable after NetCDF modules load"',
            'ncdump -h "$sample_met" > "$DEBUG_DIR/sample_met_em_header.txt"',
            "awk '",
            "  /^[[:space:]]*(byte|char|short|int|float|double)[[:space:]]+[A-Za-z_][A-Za-z0-9_]*\\(/ {",
            "    line=$0",
            "    sub(/^[[:space:]]*(byte|char|short|int|float|double)[[:space:]]+/, \"\", line)",
            "    sub(/\\(.*/, \"\", line)",
            "    print line",
            "  }",
            "' \"$DEBUG_DIR/sample_met_em_header.txt\" | sort -u > \"$DEBUG_DIR/met_em_fields.txt\"",
            'num_metgrid_levels=$(awk \'/num_metgrid_levels =/ {gsub(/[^0-9]/, "", $3); print $3; exit}\' "$DEBUG_DIR/sample_met_em_header.txt")',
            '[[ -n "$num_metgrid_levels" ]] || fail "could not extract num_metgrid_levels from $sample_met"',
            "",
            "cat > \"$DEBUG_DIR/field_check_patterns.tsv\" <<'FIELD_CHECKS'",
            field_patterns,
            "FIELD_CHECKS",
            "awk -F '\\t' '",
            "  NR == FNR { fields[$1] = 1; next }",
            "  {",
            "    status = \"FAIL\"",
            "    for (field in fields) {",
            "      if (field ~ $2) { status = \"PASS\"; break }",
            "    }",
            "    print $1 \"\\t\" status \"\\t\" $2",
            "  }",
            "' \"$DEBUG_DIR/met_em_fields.txt\" \"$DEBUG_DIR/field_check_patterns.tsv\" > \"$DEBUG_DIR/field_check.tsv\"",
            'grep -Eai "warn|error|fatal|missing|not found" ungrib.log metgrid.log > "$DEBUG_DIR/wps_warning_lines.txt" || true',
            'find "$WPS_WORK" -maxdepth 1 -type f -printf "%f\\t%s\\t%TY-%Tm-%TdT%TH:%TM:%TS\\n" | sort > "$DEBUG_DIR/wps_file_inventory.tsv"',
            'cp namelist.wps ungrib.log metgrid.log "$DEBUG_DIR"/',
            "",
            'missing_count=$(awk -F "\\t" \'$2 == "FAIL" { n++ } END { print n + 0 }\' "$DEBUG_DIR/field_check.tsv")',
            "{",
            '  printf "case\\t%s\\n" "$CASE_NAME"',
            '  printf "case_file\\t%s\\n" "$CASE_FILE"',
            '  printf "job_id\\t%s\\n" "${SLURM_JOB_ID:-none}"',
            '  printf "host\\t%s\\n" "$(hostname)"',
            '  printf "generated_utc\\t%s\\n" "$(utc_now)"',
            '  printf "wrf_commit\\t%s\\n" "$(git -C "$WRF_SRC" rev-parse --short HEAD 2>/dev/null || printf unknown)"',
            '  printf "input_root\\t%s\\n" "$INPUT_ROOT"',
            '  printf "grib_source\\t%s\\n" "$GRIB_SOURCE"',
            '  printf "grib_count\\t%s\\n" "$grib_count"',
            '  printf "wps_root\\t%s\\n" "$WPS_ROOT"',
            '  printf "vtable\\t%s\\n" "$VTABLE_NAME"',
            '  printf "prefix\\t%s\\n" "$UNGRIB_PREFIX"',
            '  printf "fg_name\\t%s\\n" "$METGRID_FG_NAME"',
            '  printf "wps_work\\t%s\\n" "$WPS_WORK"',
            '  printf "archive_dir\\t%s\\n" "$ARCHIVE_DIR"',
            '  printf "met_em_count\\t%s\\n" "$met_count"',
            '  printf "expected_met_em_count\\t%s\\n" "$EXPECTED_MET_EM_COUNT"',
            '  printf "num_metgrid_levels\\t%s\\n" "$num_metgrid_levels"',
            '  printf "field_check_failures\\t%s\\n" "$missing_count"',
            '  printf "stop_point\\tWPS-only field proof; no real.exe, wrf.exe, quicklooks, or full conveyor\\n"',
            "} > \"$DEBUG_DIR/wps_field_proof_summary.tsv\"",
            "",
            'if [[ "$missing_count" -gt 0 ]]; then',
            '  printf "RAP field proof failed: %s checklist groups missing. See %s/field_check.tsv\\n" "$missing_count" "$DEBUG_DIR" >&2',
            "  exit 3",
            "fi",
            'printf "RAP field proof passed: met_em_count=%s num_metgrid_levels=%s debug=%s\\n" "$met_count" "$num_metgrid_levels" "$DEBUG_DIR"',
            "",
        ]
    )
    return "\n".join(lines)


def render_wps_field_proof_readme(
    data: dict[str, Any],
    case_file: Path,
    *,
    output_dir: Path,
) -> str:
    case = data["case"]
    forcing = data["forcing"]
    wps = data.get("wps", {})
    paths = data["paths"]
    expected_met_em = expected_met_em_count_from_case(data)
    return "\n".join(
        [
            f"# WPS Field-Proof Packet: {case['name']}",
            "",
            "This packet is review-only until explicitly approved. It renders one",
            "WPS-only RAP field-adequacy job and does not submit Slurm, run",
            "`real.exe`, run `wrf.exe`, render quicklooks, or start the full run",
            "conveyor.",
            "",
            "## Files",
            "",
            "| File | Purpose |",
            "| --- | --- |",
            "| `wps_field_proof.slurm` | Approval-gated WPS-only proof script. |",
            "| `APPROVAL_PACKET.md` | Exact boundary, command, and evidence fields. |",
            "",
            "## Case",
            "",
            "| Field | Value |",
            "| --- | --- |",
            f"| Case file | `{case_file}` |",
            f"| Output dir | `{output_dir}` |",
            f"| Window | `{case['start']}` to `{case['end']}` |",
            f"| Domains | `{case['domains']}` |",
            f"| Forcing | `{text_value(forcing['sources'])}` |",
            f"| Interval | `{forcing['interval_seconds']}` seconds |",
            f"| Expected `met_em` count | `{expected_met_em if expected_met_em is not None else 'unknown'}` |",
            f"| WPS root | `{paths['wps_root']}` |",
            f"| Vtable | `{wps.get('vtable', 'unset')}` |",
            f"| Prefix / fg_name | `{wps.get('ungrib_prefix', 'unset')}` / `{text_value(wps.get('namelist_fg_name', forcing['wps_fg_name']))}` |",
            f"| RAP input root | `{paths['input_root']}` |",
            f"| Namelist template | `{wps.get('namelist_template', 'unset')}` |",
            f"| Geo source | `{wps.get('geogrid_source', 'unset')}` |",
            "",
            "Submit only from the shared control/output directory, not from `/tmp`,",
            "and only after the approval packet row is filled.",
            "",
        ]
    )


def render_wps_field_approval_packet(data: dict[str, Any], case_file: Path) -> str:
    case = data["case"]
    forcing = data["forcing"]
    wps = data.get("wps", {})
    paths = data["paths"]
    expected_met_em = expected_met_em_count_from_case(data)
    return "\n".join(
        [
            f"# WPS Field-Proof Approval Packet: {case['name']}",
            "",
            "## Approval Boundary",
            "",
            "| Field | Value |",
            "| --- | --- |",
            f"| Case file | `{case_file}` |",
            f"| Work | WPS-only RAP field-adequacy proof. |",
            f"| Source | `{text_value(forcing['sources'])}` |",
            f"| Vtable | `{wps.get('vtable', 'unset')}` |",
            f"| Prefix / fg_name | `{wps.get('ungrib_prefix', 'unset')}` / `{text_value(wps.get('namelist_fg_name', forcing['wps_fg_name']))}` |",
            f"| Expected files | `{expected_met_em if expected_met_em is not None else 'unknown'}` `met_em` files. |",
            "| Stop point | Report `met_em` field list, `num_metgrid_levels`, warnings, file count, and checklist result. |",
            "| Explicit no | No `real.exe`, `wrf.exe`, quicklooks, full conveyor, source staging, or downloads. |",
            "",
            "## Submit Command",
            "",
            "```bash",
            "BRC_WPS_FIELD_PROOF_APPROVED=YES sbatch wps_field_proof.slurm",
            "```",
            "",
            "## Required Inputs",
            "",
            "| Input | Path |",
            "| --- | --- |",
            f"| RAP input root | `{paths['input_root']}` |",
            f"| Manifest | `{forcing['manifest_path']}` |",
            f"| Contract | `{forcing['contract_path']}` |",
            f"| Namelist template | `{wps.get('namelist_template', 'unset')}` |",
            f"| Geo source | `{wps.get('geogrid_source', 'unset')}` |",
            "",
            "## Evidence To Fill After Completion",
            "",
            "| Item | Value |",
            "| --- | --- |",
            "| Job ID | TBD |",
            "| Slurm state / exit | TBD |",
            "| WPS archive/debug path | TBD |",
            "| `met_em` count | TBD |",
            "| `num_metgrid_levels` | TBD |",
            "| Missing checklist groups | TBD |",
            "| Warning summary | TBD |",
            "| RAP-alone disposition | TBD: viable / missing fields / rerun with different Vtable / needs filler. |",
            "",
        ]
    )


def write_wps_field_proof_packet(
    data: dict[str, Any],
    case_file: Path,
    *,
    output_dir: Path,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        output_dir / "README.md": render_wps_field_proof_readme(
            data,
            case_file,
            output_dir=output_dir,
        ),
        output_dir / "APPROVAL_PACKET.md": render_wps_field_approval_packet(data, case_file),
        output_dir / "wps_field_proof.slurm": render_wps_field_proof_slurm(data, case_file),
    }
    for path, text in paths.items():
        path.write_text(text + ("\n" if not text.endswith("\n") else ""), encoding="utf-8")
    return list(paths)


def parse_csv_ints(raw: str) -> list[int]:
    values: list[int] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        value = int(item)
        if value <= 0:
            raise ValueError(f"task counts must be positive: {raw}")
        values.append(value)
    if not values:
        raise ValueError("at least one task count is required")
    return values


def parse_csv_strings(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def practical_variant(
    data: dict[str, Any],
    *,
    scenario: str,
    job_suffix: str,
    ntasks: int | None = None,
    memory: str | None = None,
) -> dict[str, Any]:
    variant = copy.deepcopy(data)
    slurm = variant["slurm"]
    paths = variant["paths"]
    archive_root = as_path(paths["archive_root"])
    run_root = as_path(paths["run_root"])

    slurm["profile"] = "gate11_practical_review"
    slurm["job_name"] = f"{slurm['job_name']}_{job_suffix}"
    if ntasks is not None:
        slurm["ntasks"] = ntasks
    if memory is not None:
        slurm["memory"] = memory

    scenario_name = safe_name(scenario)
    paths["wrf_run"] = str(run_root / "practical_tests" / scenario_name / "wrf_run")
    paths["archive_root"] = str(archive_root / "practical_tests" / scenario_name)
    return variant


def practical_scenario_record(
    *,
    scenario: str,
    kind: str,
    script_name: str,
    description: str,
    variant: dict[str, Any],
) -> dict[str, str]:
    slurm = variant["slurm"]
    paths = variant["paths"]
    return {
        "scenario": safe_name(scenario),
        "kind": kind,
        "script": script_name,
        "description": description,
        "tasks": str(slurm["ntasks"]),
        "memory": str(slurm["memory"]),
        "wrf_run": str(paths["wrf_run"]),
        "archive_root": str(paths["archive_root"]),
    }


def render_prepare_checklist(
    data: dict[str, Any],
    case_file: Path,
    *,
    scenarios: list[dict[str, str]],
) -> str:
    case = data["case"]
    paths = data["paths"]
    source_wrf_run = str(as_path(paths["wrf_run"]))
    john_wrf_build = str(as_path(paths["wrf_build"]))
    john_real = str(as_path(paths["wrf_build"]) / "main" / "real.exe")
    john_wrf = str(as_path(paths["wrf_build"]) / "main" / "wrf.exe")

    lines = [
        f"# Gate 11 Scenario Prepare/Check Plan: {case['name']}",
        "",
        "This is a preparation plan, not approval to copy files, inspect heavy",
        "artifacts, submit Slurm, run WPS, run `real.exe`, or run `wrf.exe`.",
        "Any command that reads or copies scratch/archive WRF artifacts belongs",
        "inside an approved batch, DTN, or interactive compute context.",
        "",
        "## Scenario Targets",
        "",
        "| Scenario | Script | Tasks | Memory | Target `WRF_RUN` | Target archive root |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for record in scenarios:
        lines.append(
            f"| {record['scenario']} | `{record['script']}` | {record['tasks']} | "
            f"`{record['memory']}` | `{record['wrf_run']}` | `{record['archive_root']}` |"
        )

    lines.extend(
        [
            "",
            "## Source Artifacts",
            "",
            "Use John's compiled WRF build as the executable source, and use the",
            "approved NAM-only Gate 7/8 WRF run directory only for run artifacts",
            "such as `namelist.input` and `met_em` files. The case manifest",
            f"names John's WRF build as `{john_wrf_build}` and currently names",
            f"the default artifact source candidate as `{source_wrf_run}`.",
            "Before any copy or symlink operation, confirm artifact sources are",
            "not Michael-owned comparison paths and not repo-local scratch areas.",
            "",
            "| Required in each target `WRF_RUN` | Source class | Notes |",
            "| --- | --- | --- |",
            f"| `real.exe` | John-owned WRF build | Source from `{john_real}`; wrappers byte-compare before `real.exe`. |",
            f"| `wrf.exe` | John-owned WRF build | Source from `{john_wrf}`; wrappers byte-compare before `real.exe`. |",
            f"| WRF runtime files | John-owned WRF `run/` directory | Stage from `{john_wrf_build}/run/`; current-case preflight requires and byte-compares `{', '.join(REQUIRED_WRF_RUNTIME_FILES)}`. |",
            "| `namelist.input` | Proven NAM-only WRF run setup | Keep source SHA, WRF/WPS roots, and case window unchanged across benchmark rows. |",
            "| `met_em.d0*.nc` | Gate 6 WPS output consumed by the proven run | Do not inspect or copy on a login node. |",
            "",
            "Do not pre-copy `wrfout_d0*` into a scenario directory. Each approved",
            "benchmark row must produce its own WRF output and archive evidence.",
            "",
            "## Approved-Context Preparation Template",
            "",
            "Use this only after a human approves the file-copy context. Fill",
            "`PROVEN_WRF_RUN` from the checked Gate 7/8 evidence path, choose one",
            "`SCENARIO`, and set `WRF_RUN` from the target table above.",
            "",
            "```bash",
            "# Approved batch, DTN, or interactive compute context only.",
            "# Do not run this from a login node.",
            f"CASE_FILE={shell_quote(case_file)}",
            f"JOHN_WRF_BUILD={shell_quote(john_wrf_build)}",
            "PROVEN_WRF_RUN=/path/to/approved/gate7_or_gate8/wrf_run",
            "SCENARIO=baseline",
            "WRF_RUN=/path/from/the/scenario-target-table",
            "",
            'test -x "$JOHN_WRF_BUILD/main/real.exe"',
            'test -x "$JOHN_WRF_BUILD/main/wrf.exe"',
            'mkdir -p "$WRF_RUN"',
            'rsync -av "$JOHN_WRF_BUILD"/main/real.exe "$WRF_RUN"/',
            'rsync -av "$JOHN_WRF_BUILD"/main/wrf.exe "$WRF_RUN"/',
            'rsync -av --exclude="*.exe" "$JOHN_WRF_BUILD"/run/ "$WRF_RUN"/',
            'rsync -av "$PROVEN_WRF_RUN"/namelist.input "$WRF_RUN"/',
            'rsync -av "$PROVEN_WRF_RUN"/met_em.d0*.nc "$WRF_RUN"/',
            "```",
            "",
            "## Approved-Context Pre-Submit Check",
            "",
            "The rendered Slurm wrappers repeat these checks and fail fast. Run this",
            "manual check only in the same approved context as the preparation copy.",
            "",
            "```bash",
            'test -x "$WRF_RUN/real.exe"',
            'test -x "$WRF_RUN/wrf.exe"',
            'test -f "$WRF_RUN/namelist.input"',
            'compgen -G "$WRF_RUN/met_em.d0*.nc" >/dev/null',
            'cmp -s "$JOHN_WRF_BUILD/main/real.exe" "$WRF_RUN/real.exe"',
            'cmp -s "$JOHN_WRF_BUILD/main/wrf.exe" "$WRF_RUN/wrf.exe"',
            f"for runtime_file in {' '.join(REQUIRED_WRF_RUNTIME_FILES)}; do",
            '  test -f "$JOHN_WRF_BUILD/run/$runtime_file"',
            '  test -f "$WRF_RUN/$runtime_file"',
            '  cmp -s "$JOHN_WRF_BUILD/run/$runtime_file" "$WRF_RUN/$runtime_file"',
            "done",
            "```",
            "",
            "## Login-Safe Review",
            "",
            "From a login node, review this checklist, the generated Slurm text, and",
            "`APPROVAL_PACKET.md` only. Do not hash manifests, inspect NetCDF, list",
            "large scratch directories, copy `met_em`, or run quicklook checks.",
            "",
        ]
    )
    return "\n".join(lines)


def render_prepare_script(
    data: dict[str, Any],
    case_file: Path,
    *,
    record: dict[str, str],
) -> str:
    paths = data["paths"]
    source_wrf_run = str(as_path(paths["wrf_run"]))
    john_wrf_build = str(as_path(paths["wrf_build"]))
    scenario = record["scenario"]
    wrf_run = record["wrf_run"]

    lines = [
        "#!/bin/bash",
        f"# Rendered by brc-cases/wrf_case.py from {case_file}",
        "# Approved batch, DTN, or interactive compute context only.",
        "# Copies/checks files only; does not submit Slurm or run real.exe/wrf.exe.",
        "set -euo pipefail",
        "",
        'fail() { printf "ERROR: %s\\n" "$*" >&2; exit 2; }',
        '[[ "${BRC_PREP_APPROVED:-NO}" == "YES" ]] || fail "set BRC_PREP_APPROVED=YES only inside an approved batch/DTN/interactive compute context"',
        "",
        f"CASE_FILE={shell_quote(case_file)}",
        f"SCENARIO={shell_quote(scenario)}",
        f"JOHN_WRF_BUILD={shell_quote(john_wrf_build)}",
        f"WRF_RUN={shell_quote(wrf_run)}",
        'if [[ -z "${PROVEN_WRF_RUN:-}" ]]; then',
        f"  PROVEN_WRF_RUN={shell_quote(source_wrf_run)}",
        "fi",
        "",
        'case "$JOHN_WRF_BUILD" in *"/u6060939/"*) fail "JOHN_WRF_BUILD points into Michael-owned comparison path: $JOHN_WRF_BUILD" ;; esac',
        'case "$PROVEN_WRF_RUN" in *"/u6060939/"*) fail "PROVEN_WRF_RUN points into Michael-owned comparison path: $PROVEN_WRF_RUN" ;; esac',
        '[[ "$WRF_RUN/" != "$JOHN_WRF_BUILD/"* ]] || fail "WRF_RUN must not live inside the WRF checkout: $WRF_RUN"',
        "",
        'test -x "$JOHN_WRF_BUILD/main/real.exe"',
        'test -x "$JOHN_WRF_BUILD/main/wrf.exe"',
        'test -d "$JOHN_WRF_BUILD/run"',
        'test -f "$PROVEN_WRF_RUN/namelist.input"',
        'compgen -G "$PROVEN_WRF_RUN/met_em.d0*.nc" >/dev/null',
        f"for runtime_file in {' '.join(REQUIRED_WRF_RUNTIME_FILES)}; do",
        '  test -f "$JOHN_WRF_BUILD/run/$runtime_file"',
        "done",
        "",
        'mkdir -p "$WRF_RUN"',
        'rsync -av "$JOHN_WRF_BUILD"/main/real.exe "$WRF_RUN"/',
        'rsync -av "$JOHN_WRF_BUILD"/main/wrf.exe "$WRF_RUN"/',
        'rsync -av --exclude="*.exe" "$JOHN_WRF_BUILD"/run/ "$WRF_RUN"/',
        'rsync -av "$PROVEN_WRF_RUN"/namelist.input "$WRF_RUN"/',
        'rsync -av "$PROVEN_WRF_RUN"/met_em.d0*.nc "$WRF_RUN"/',
        "",
        'test -x "$WRF_RUN/real.exe"',
        'test -x "$WRF_RUN/wrf.exe"',
        'test -f "$WRF_RUN/namelist.input"',
        'compgen -G "$WRF_RUN/met_em.d0*.nc" >/dev/null',
        'cmp -s "$JOHN_WRF_BUILD/main/real.exe" "$WRF_RUN/real.exe"',
        'cmp -s "$JOHN_WRF_BUILD/main/wrf.exe" "$WRF_RUN/wrf.exe"',
        f"for runtime_file in {' '.join(REQUIRED_WRF_RUNTIME_FILES)}; do",
        '  test -f "$WRF_RUN/$runtime_file"',
        '  cmp -s "$JOHN_WRF_BUILD/run/$runtime_file" "$WRF_RUN/$runtime_file"',
        "done",
        "",
        'SUMMARY="${WRF_RUN}/brc_prepare_summary.tsv"',
        "{",
        '  printf "key\\tvalue\\n"',
        '  printf "scenario\\t%s\\n" "$SCENARIO"',
        '  printf "case_file\\t%s\\n" "$CASE_FILE"',
        '  printf "john_wrf_build\\t%s\\n" "$JOHN_WRF_BUILD"',
        '  printf "proven_wrf_run\\t%s\\n" "$PROVEN_WRF_RUN"',
        '  printf "wrf_run\\t%s\\n" "$WRF_RUN"',
        '  printf "prepared_utc\\t%s\\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"',
        "} > \"$SUMMARY\"",
        'printf "prepared scenario=%s wrf_run=%s summary=%s\\n" "$SCENARIO" "$WRF_RUN" "$SUMMARY"',
        "",
    ]
    return "\n".join(lines)


def render_approval_packet(
    data: dict[str, Any],
    case_file: Path,
    *,
    scenarios: list[dict[str, str]],
) -> str:
    case = data["case"]
    forcing = data["forcing"]
    scaling = [record for record in scenarios if record["kind"] == "scaling"]
    memory = [record for record in scenarios if record["kind"] == "memory"]
    baseline = [record for record in scenarios if record["kind"] == "baseline"]

    lines = [
        f"# Gate 11 Benchmark Approval Packet: {case['name']}",
        "",
        "This packet is a no-run approval surface. A rendered script is not",
        "approval to submit. Fill one row before `sbatch`, and fill the evidence",
        "fields only after the approved run finishes and artifacts are checked in",
        "the appropriate compute/batch context.",
        "",
        "## Approval Boundary",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Case file | `{case_file}` |",
        f"| Case window | `{case['start']}` to `{case['end']}` |",
        f"| Forcing | `{text_value(forcing['sources'])}` |",
        f"| WPS fg_name | `{text_value(forcing['wps_fg_name'])}` |",
        f"| WPS cadence | `{forcing['interval_seconds']}` seconds |",
        "| Submit boundary | Human approval required before `sbatch`, WPS, `real.exe`, or `wrf.exe`. |",
        "| Artifact-read boundary | Strict validation, NetCDF/archive reads, and quicklooks require approved off-login context. |",
        "",
        "## Evidence Columns",
        "",
        "Every completed benchmark row must record: job ID, Slurm state, WRF",
        "marker, wall time, simulated hours, peak memory evidence, archive path,",
        "debug path, and recommendation.",
        "",
    ]

    if str(case["name"]) == "jan2013_basin_gefs":
        lines.extend(
            [
                "## Current Practical Evidence",
                "",
                "| Scenario | Status | Evidence |",
                "| --- | --- | --- |",
                "| `scaling_t028` | Completed with John's WRF `V4.8.0`, 28 tasks, `900G`; `real.exe`, `wrf.exe`, archive, and debug summary exited `0`. | `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_archive/jan2013_basin_gefs/practical_tests/scaling_t028/run_20260618T230858Z/debug/` |",
                "| `scaling_t016` | Job `13550555` failed before WRF runtime evidence after being submitted from a node-local `/tmp` packet; Slurm state `FAILED`, exit `2:0`, elapsed `00:00:04`, no `rsl.*`, no archive, no debug path. | Rerendered scripts now use shared Slurm `--chdir` and stdout/stderr. |",
                "| `scaling_t016` | Job `13550909` used the shared log path and failed before `real.exe`; Slurm state `FAILED`, exit `2:0`, elapsed `00:00:04` on `notch392`. The target run directory had `real.exe`, `wrf.exe`, and `namelist.input`, but lacked all required runtime physics/table files from John's `run/` directory. | Log: `/uufs/chpc.utah.edu/common/home/lawson-group6/jrlawson/wrf_build_logs/brc-wrf/wrf_jan2013_nam_t016_13550909.out`; no `rsl.*`, archive, or debug path. Prepare that scenario `WRF_RUN` before any retry. |",
                "",
                "Do not rerun `scaling_t028` by default. The approval rows below are",
                "templates; fill exactly one unapproved row before any new `sbatch`.",
                "",
            ]
        )

    def append_rows(title: str, records: list[dict[str, str]], empty_note: str) -> None:
        lines.extend(
            [
                f"## {title}",
                "",
                "| Scenario | Script | Tasks | Memory request | Approval status | Approved by/date | Job ID | Slurm state | WRF marker | Wall time | Sim hours | Peak memory evidence | Archive path | Debug path | Recommendation |",
                "| --- | --- | ---: | ---: | --- | --- | --- | --- | --- | ---: | ---: | --- | --- | --- | --- |",
            ]
        )
        if not records:
            lines.append(empty_note)
        for record in records:
            archive_run = f"{record['archive_root']}/run_<UTC>_<jobid>"
            debug_path = f"{archive_run}/debug/"
            lines.append(
                f"| {record['scenario']} | `{record['script']}` | {record['tasks']} | "
                f"`{record['memory']}` | not approved | TBD | TBD | TBD | TBD | "
                f"TBD | TBD | TBD | `{archive_run}` | `{debug_path}` | TBD |"
            )
        lines.append("")

    append_rows(
        "Baseline Approval Row",
        baseline,
        "| TBD | TBD | TBD | TBD | not approved | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |",
    )
    append_rows(
        "Scaling Approval Rows",
        scaling,
        "| TBD | Rerender with `--tasks` | TBD | TBD | not approved | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |",
    )
    append_rows(
        "Memory Approval Rows",
        memory,
        "| memory_candidate_tbd | Rerender with `--memory-candidates <mem1,mem2>` | TBD | TBD | not approved | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |",
    )

    lines.extend(
        [
            "## Recommendation Rule",
            "",
            "Do not write a recommendation until the row has a completed Slurm",
            "state, a `SUCCESS COMPLETE WRF` marker, wall-time evidence, simulated",
            "hours, peak memory evidence, archive path, and debug path. If archive",
            "work fails after WRF succeeds, record WRF success and archive failure as",
            "separate facts.",
            "",
        ]
    )
    return "\n".join(lines)


def render_practical_packet(
    data: dict[str, Any],
    case_file: Path,
    *,
    output_dir: Path,
    scripts: list[tuple[str, str]],
    prep_scripts: list[tuple[str, str]],
    scenarios: list[dict[str, str]],
) -> str:
    case = data["case"]
    forcing = data["forcing"]
    paths = data["paths"]
    slurm = data["slurm"]
    case_name = str(case["name"])

    lines = [
        f"# Gate 11 Practical-Test Harness: {case_name}",
        "",
        "Rendered from the tracked case manifest. This packet is review-only; it",
        "does not submit Slurm, run WPS, run `real.exe`, run `wrf.exe`, read",
        "NetCDF/archive artifacts, hash staged inputs, or render quicklooks.",
        "",
        "## Case Contract",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Case file | `{case_file}` |",
        f"| Render output | `{output_dir}` |",
        f"| Window | `{case['start']}` to `{case['end']}` |",
        f"| Domains | `{case['domains']}` |",
        f"| Forcing | `{text_value(forcing['sources'])}` |",
        f"| WPS cadence | `{forcing['interval_seconds']}` seconds |",
        f"| WPS fg_name | `{text_value(forcing['wps_fg_name'])}` |",
        f"| Manifest | `{forcing['manifest_path']}` |",
        f"| Contract | `{forcing['contract_path']}` |",
        f"| WRF source | `{paths['wrf_src']}` |",
        f"| WPS root | `{paths['wps_root']}` |",
        f"| Scratch run root | `{paths['run_root']}` |",
        f"| Archive root | `{paths['archive_root']}` |",
        f"| Default Slurm | `{slurm['account']}` / `{slurm['partition']}`, `{slurm.get('nodelist', 'any')}`, `{slurm['nodes']}` node, `{slurm['ntasks']}` tasks, `{slurm['memory']}` |",
        f"| Launcher | `{slurm['mpi_launcher']}` |",
        "",
        "## Packet Files",
        "",
        "| File | Purpose |",
        "| --- | --- |",
        "| `README.md` | Overview, render commands, result tables, and closeout record. |",
        "| `PREPARE_CHECKLIST.md` | Per-scenario `WRF_RUN` targets and approved-context preparation/check plan. |",
        "| `APPROVAL_PACKET.md` | No-run approval rows for baseline, scaling, and memory candidates. |",
        "| `prepare_<scenario>.sh` | Approved-context copy/check helpers; require `BRC_PREP_APPROVED=YES`. |",
        "",
        "## Rendered Scripts",
        "",
        "| Script | Scenario | Approval boundary |",
        "| --- | --- | --- |",
    ]
    for script, scenario in scripts:
        lines.append(
            f"| `{script}` | {scenario} | Human approval before `sbatch`; run only in approved Slurm/compute context. |"
        )

    lines.extend(
        [
            "",
            "## Rendered Prepare Scripts",
            "",
            "| Script | Scenario | Approval boundary |",
            "| --- | --- | --- |",
        ]
    )
    for script, scenario in prep_scripts:
        lines.append(
            f"| `{script}` | {scenario} | Human approval plus `BRC_PREP_APPROVED=YES`; copy/check only in approved compute/DTN context. |"
        )

    lines.extend(
        [
            "",
            "Each script preserves the maintained wrapper behavior from",
            "`brc-cases/wrf_case.py render-slurm`: settings readback, module",
            "record, phase timings, file inventory, `real.exe` and `wrf.exe`",
            "success-marker checks, colon-safe `wrfout` archive copy, and debug",
            "archive under `debug/`.",
            "",
            "The scaling variants use per-scenario scratch and archive roots under",
            "`practical_tests/<scenario>/` so benchmark results do not collide",
            "with the proof archive or with each other.",
            "",
            f"Practical scripts set Slurm's working directory, stdout, and stderr",
            f"to the shared log root `{PRACTICAL_SLURM_LOG_ROOT}` so early scheduler",
            "or wrapper failures remain visible even when the review packet itself",
            "lives under node-local `/tmp`.",
            "",
            "`PREPARE_CHECKLIST.md` names every per-scenario `WRF_RUN` and explains",
            "how to stage `real.exe` and `wrf.exe` from John's WRF build, plus",
            "runtime physics files from John's WRF `run/` directory, plus",
            "`namelist.input` and `met_em` files from the approved proven run",
            "artifacts. The rendered scripts fail fast if those inputs are",
            "missing, if the current-case runtime files are absent or do not",
            "byte-match `paths.wrf_build/run`, or if the scenario executables",
            "do not byte-match `paths.wrf_build/main`.",
            "",
            "`APPROVAL_PACKET.md` carries the no-run approval rows and evidence",
            "fields for baseline, 16/28/56-style scaling rows, and optional memory",
            "candidates. Fill those rows only after an approved run produces",
            "evidence.",
            "",
            "## Login-Safe Checks",
            "",
            "Run these before requesting approval. They are metadata/render checks",
            "only when `--strict-files` is omitted.",
            "",
            "```bash",
            f"python brc-cases/wrf_case.py validate {case_file}",
            f"python brc-cases/wrf_case.py render-practical-harness {case_file} --output-dir {shell_quote(output_dir)}",
            f"bash -n {shell_quote(output_dir)}/*.slurm",
            "```",
            "",
            "## Off-Login Checks",
            "",
            "Use only inside an approved batch, DTN, or interactive compute context",
            "when the command reads staged inputs, manifests, WPS/WRF files,",
            "NetCDF, archives, or quicklook outputs.",
            "",
            "```bash",
            "cd ../brc-tools",
            f"conda run -n brc-tools-2026 python -m brc_tools.nwp.wrf_staging --verify-manifest {forcing['manifest_path']}",
            "cd ../brc-wrf",
            f"python brc-cases/wrf_case.py validate {case_file} --strict-files",
            f"python brc-cases/wrf_quicklook.py check {case_file}",
            f"python brc-cases/wrf_quicklook.py render {case_file}",
            "```",
            "",
            "## Scaling Result Table",
            "",
            "| Scenario | Tasks | Memory request | Job ID | Slurm state | WRF marker | Wall time | Sim hours | Peak memory evidence | Archive path | Debug path | Recommendation |",
            "| --- | ---: | --- | --- | --- | --- | ---: | ---: | --- | --- | --- | --- |",
        ]
    )
    for record in scenarios:
        if record["kind"] != "scaling":
            continue
        archive_run = f"{record['archive_root']}/run_<UTC>_<jobid>"
        debug_path = f"{archive_run}/debug/"
        lines.append(
            f"| {record['scenario']} | {record['tasks']} | `{record['memory']}` | "
            f"TBD | TBD | TBD | TBD | TBD | TBD | `{archive_run}` | `{debug_path}` | TBD |"
        )

    lines.extend(
        [
            "",
            "## Memory Result Table",
            "",
            "| Scenario | Tasks | Memory request | Job ID | Slurm state | WRF marker | Wall time | Sim hours | Peak memory evidence | Archive path | Debug path | Recommendation |",
            "| --- | ---: | --- | --- | --- | --- | ---: | ---: | --- | --- | --- | --- |",
        ]
    )
    memory_rows = [record for record in scenarios if record["kind"] == "memory"]
    if memory_rows:
        for record in memory_rows:
            archive_run = f"{record['archive_root']}/run_<UTC>_<jobid>"
            debug_path = f"{archive_run}/debug/"
            lines.append(
                f"| {record['scenario']} | {record['tasks']} | `{record['memory']}` | "
                f"TBD | TBD | TBD | TBD | TBD | TBD | `{archive_run}` | `{debug_path}` | TBD |"
            )
    else:
        lines.append("| memory_candidate_tbd | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |")

    lines.extend(
        [
            "",
            "## Closeout Record",
            "",
            "| Field | Value |",
            "| --- | --- |",
            "| Gate/item | Gate 11 practical-test harness or approved benchmark row |",
            "| Commands run | Exact render/check commands and any approved `sbatch` |",
            "| Host/context | Login render, DTN, interactive compute, or Slurm job ID |",
            "| Approval status | Who approved WPS/WRF/Slurm, or `not approved/not run` |",
            "| Evidence paths | Render packet, Slurm logs, manifest, contract, archive, quicklooks |",
            "| Owner repo | `brc-wrf` for wrapper/run; `brc-tools` for staging; `brc-knowledge` for CHPC truth |",
            "| Result | Passed, failed, parked, or not run |",
            "| What was not run | Explicit skipped compute/artifact reads |",
            "| Dirty state | `git status --short --branch --untracked-files=all` |",
            "| Commit/push status | SHA and remote branch when applicable |",
            "| Next suggested item | Next approval row or design task |",
            "",
            "Do not treat a successful render as approval to submit. Practical",
            "benchmark `sbatch`, WPS, `real.exe`, `wrf.exe`, strict artifact reads,",
            "and quicklooks remain approval-gated.",
            "",
        ]
    )
    return "\n".join(lines)


def print_findings(findings: list[Finding]) -> None:
    if not findings:
        print("OK: no findings")
        return
    for finding in findings:
        print(f"{finding.severity}: {finding.message}")


def require_outside_repo(path: Path, repo_root: Path, label: str) -> None:
    if path_under(path, repo_root):
        raise ValueError(f"{label} must stay outside the brc-wrf checkout: {path}")


def write_practical_harness(
    data: dict[str, Any],
    case_file: Path,
    *,
    output_dir: Path,
    tasks: list[int],
    memory_candidates: list[str],
) -> PracticalHarnessResult:
    output_dir.mkdir(parents=True, exist_ok=True)

    scripts: list[tuple[str, str]] = []
    prep_scripts: list[tuple[str, str]] = []
    scenarios: list[dict[str, str]] = []
    script_paths: list[Path] = []
    prep_script_paths: list[Path] = []
    baseline = practical_variant(
        data,
        scenario="baseline",
        job_suffix="baseline",
    )
    baseline_name = "baseline.slurm"
    baseline_path = output_dir / baseline_name
    baseline_path.write_text(render_slurm(baseline, case_file), encoding="utf-8")
    script_paths.append(baseline_path)
    baseline_description = "baseline current case profile"
    scripts.append((baseline_name, baseline_description))
    scenarios.append(
        practical_scenario_record(
            scenario="baseline",
            kind="baseline",
            script_name=baseline_name,
            description=baseline_description,
            variant=baseline,
        )
    )

    for task_count in tasks:
        scenario = f"scaling_t{task_count:03d}"
        script_name = f"{scenario}.slurm"
        variant = practical_variant(
            data,
            scenario=scenario,
            job_suffix=f"t{task_count:03d}",
            ntasks=task_count,
        )
        script_path = output_dir / script_name
        script_path.write_text(render_slurm(variant, case_file), encoding="utf-8")
        script_paths.append(script_path)
        description = f"scaling candidate: {task_count} tasks"
        scripts.append((script_name, description))
        scenarios.append(
            practical_scenario_record(
                scenario=scenario,
                kind="scaling",
                script_name=script_name,
                description=description,
                variant=variant,
            )
        )

    for memory in memory_candidates:
        scenario = f"memory_{safe_name(memory)}"
        script_name = f"{scenario}.slurm"
        variant = practical_variant(
            data,
            scenario=scenario,
            job_suffix=f"mem{safe_name(memory)}",
            memory=memory,
        )
        script_path = output_dir / script_name
        script_path.write_text(render_slurm(variant, case_file), encoding="utf-8")
        script_paths.append(script_path)
        description = f"memory candidate: {memory}"
        scripts.append((script_name, description))
        scenarios.append(
            practical_scenario_record(
                scenario=scenario,
                kind="memory",
                script_name=script_name,
                description=description,
                variant=variant,
            )
        )

    for record in scenarios:
        prep_name = f"prepare_{record['scenario']}.sh"
        prep_path = output_dir / prep_name
        prep_path.write_text(
            render_prepare_script(data, case_file, record=record),
            encoding="utf-8",
        )
        prep_path.chmod(0o755)
        prep_script_paths.append(prep_path)
        prep_scripts.append((prep_name, record["description"]))

    packet_name = "README.md"
    packet_path = output_dir / packet_name
    packet_path.write_text(
        render_practical_packet(
            data,
            case_file,
            output_dir=output_dir,
            scripts=scripts,
            prep_scripts=prep_scripts,
            scenarios=scenarios,
        ),
        encoding="utf-8",
    )
    prepare_name = "PREPARE_CHECKLIST.md"
    prepare_path = output_dir / prepare_name
    prepare_path.write_text(
        render_prepare_checklist(data, case_file, scenarios=scenarios),
        encoding="utf-8",
    )
    approval_name = "APPROVAL_PACKET.md"
    approval_path = output_dir / approval_name
    approval_path.write_text(
        render_approval_packet(data, case_file, scenarios=scenarios),
        encoding="utf-8",
    )
    return PracticalHarnessResult(
        output_dir=output_dir,
        scripts=script_paths,
        packet_files=[packet_path, prepare_path, approval_path],
        prep_scripts=prep_script_paths,
    )


def run_capture(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def completed_status(result: subprocess.CompletedProcess[str]) -> str:
    return "PASS" if result.returncode == 0 else f"FAIL ({result.returncode})"


def render_no_run_report(
    data: dict[str, Any],
    case_file: Path,
    *,
    output_path: Path,
    packet_dir: Path,
    standalone_slurm: Path,
    validation_findings: list[Finding],
    harness_result: PracticalHarnessResult,
    shell_check: subprocess.CompletedProcess[str],
    packet_status: str,
    repo_root: Path,
) -> str:
    case = data["case"]
    forcing = data["forcing"]
    slurm = data["slurm"]
    utc = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    branch = run_capture(["git", "branch", "--show-current"], cwd=repo_root)
    head = run_capture(["git", "rev-parse", "--short", "HEAD"], cwd=repo_root)
    status = run_capture(
        ["git", "status", "--short", "--branch", "--untracked-files=all"],
        cwd=repo_root,
    )
    hostname = run_capture(["hostname"], cwd=repo_root)
    validation_status = (
        "PASS"
        if not any(finding.severity == "ERROR" for finding in validation_findings)
        else "FAIL"
    )
    finding_lines = (
        [f"- {finding.severity}: {finding.message}" for finding in validation_findings]
        if validation_findings
        else ["- OK: no findings"]
    )
    shell_output = (shell_check.stdout + shell_check.stderr).strip()
    shell_lines = shell_output.splitlines() if shell_output else ["- no output"]

    lines = [
        f"# BRC WRF No-Run Report: {case['name']}",
        "",
        "This report is login-node-safe. It validates case metadata, renders",
        "review-only Slurm and Gate 11 packet artifacts outside the repo, and",
        "checks rendered shell syntax. It does not read staged manifests, NetCDF,",
        "archives, quicklooks, or submit WPS/WRF/Slurm work.",
        "",
        "## Source State",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Generated UTC | `{utc}` |",
        f"| Host | `{hostname.stdout.strip() or 'unknown'}` |",
        f"| Branch | `{branch.stdout.strip() or 'unknown'}` |",
        f"| Commit | `{head.stdout.strip() or 'unknown'}` |",
        f"| Case file | `{case_file}` |",
        f"| Report | `{output_path}` |",
        f"| Gate 11 packet | `{packet_dir}` |",
        f"| Standalone Slurm render | `{standalone_slurm}` |",
        "",
        "## Case Snapshot",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Window | `{case['start']}` to `{case['end']}` |",
        f"| Domains | `{case['domains']}` |",
        f"| Forcing | `{text_value(forcing['sources'])}` |",
        f"| WPS fg_name | `{text_value(forcing['wps_fg_name'])}` |",
        f"| WPS cadence | `{forcing['interval_seconds']}` seconds |",
        f"| Slurm default | `{slurm['account']}` / `{slurm['partition']}`, `{slurm.get('nodelist', 'any')}`, `{slurm['nodes']}` node, `{slurm['ntasks']}` tasks, `{slurm['memory']}` |",
        f"| Launcher | `{slurm['mpi_launcher']}` |",
        "",
        "## Login-Safe Results",
        "",
        "| Check | Result |",
        "| --- | --- |",
        f"| Case metadata validation | `{validation_status}` |",
        f"| Gate 11 packet render | `{packet_status}` |",
        f"| Rendered shell syntax | `{completed_status(shell_check)}` |",
        "",
        "## Validation Findings",
        "",
        *finding_lines,
        "",
        "## Rendered Artifacts",
        "",
        "| Artifact | Path |",
        "| --- | --- |",
    ]
    for path in (
        harness_result.packet_files
        + harness_result.prep_scripts
        + harness_result.scripts
        + [standalone_slurm]
    ):
        lines.append(f"| `{path.name}` | `{path}` |")

    lines.extend(
        [
            "",
            "## Shell Syntax Output",
            "",
            "```text",
            *shell_lines,
            "```",
            "",
            "## Git Status",
            "",
            "```text",
            status.stdout.strip() or "(clean status output unavailable)",
            "```",
            "",
            "## Stop Point",
            "",
            "Not run: `--strict-files`, manifest hashing, NetCDF/archive reads,",
            "quicklook check/render, WPS, `real.exe`, `wrf.exe`, `sbatch`, scaling",
            "sweeps, memory benchmarks, or scratch/archive copy operations.",
            "",
            "Recommended next gate: use `APPROVAL_PACKET.md` to approve exactly one",
            "benchmark row after row-specific prepare checks. Because `scaling_t028`",
            "already passed and `scaling_t016` has not reached `real.exe`, the next",
            "single row remains `scaling_t016` after preparing its `WRF_RUN` from",
            "John-owned build and runtime files.",
            "",
        ]
    )
    return "\n".join(lines)


def cmd_validate(args: argparse.Namespace) -> int:
    case_file = Path(args.case_file)
    data = load_case(case_file)
    findings = validate_case(data, strict_files=args.strict_files)
    print_findings(findings)
    return 1 if any(f.severity == "ERROR" for f in findings) else 0


def cmd_render_slurm(args: argparse.Namespace) -> int:
    case_file = Path(args.case_file)
    data = load_case(case_file)
    findings = validate_case(data, strict_files=False)
    findings.extend(run_readiness_findings(data))
    errors = [f for f in findings if f.severity == "ERROR"]
    if errors:
        print_findings(errors)
        return 1
    text = render_slurm(data, case_file)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


def cmd_render_practical_harness(args: argparse.Namespace) -> int:
    case_file = Path(args.case_file)
    output_dir = Path(args.output_dir)
    data = load_case(case_file)
    findings = validate_case(data, strict_files=False)
    findings.extend(run_readiness_findings(data))
    errors = [f for f in findings if f.severity == "ERROR"]
    if errors:
        print_findings(errors)
        return 1

    repo_root = as_path(data["paths"]["wrf_src"])
    require_outside_repo(output_dir, repo_root, "practical harness output")

    tasks = parse_csv_ints(args.tasks)
    memory_candidates = parse_csv_strings(args.memory_candidates)
    result = write_practical_harness(
        data,
        case_file,
        output_dir=output_dir,
        tasks=tasks,
        memory_candidates=memory_candidates,
    )
    print(f"Wrote Gate 11 practical-test harness packet: {output_dir}")
    for path in result.prep_scripts:
        print(f"  {path}")
    for path in result.scripts:
        print(f"  {path}")
    for path in result.packet_files:
        print(f"  {path}")
    return 0


def cmd_render_no_run_report(args: argparse.Namespace) -> int:
    case_file = Path(args.case_file)
    data = load_case(case_file)
    case_name = safe_name(data["case"]["name"])
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    output_path = (
        Path(args.output)
        if args.output
        else Path("/tmp") / f"brc_wrf_no_run_report_{case_name}_{stamp}.md"
    )
    packet_dir = (
        Path(args.packet_dir)
        if args.packet_dir
        else output_path.with_suffix("").parent / f"{output_path.with_suffix('').name}_gate11_packet"
    )
    standalone_slurm = (
        Path(args.slurm_output)
        if args.slurm_output
        else output_path.with_suffix("").parent / f"{output_path.with_suffix('').name}_render.slurm"
    )
    repo_root = as_path(data["paths"]["wrf_src"])
    require_outside_repo(output_path, repo_root, "no-run report output")
    require_outside_repo(packet_dir, repo_root, "no-run packet output")
    require_outside_repo(standalone_slurm, repo_root, "standalone Slurm output")

    findings = validate_case(data, strict_files=False)
    findings.extend(run_readiness_findings(data))
    errors = [finding for finding in findings if finding.severity == "ERROR"]
    if errors:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            render_no_run_report(
                data,
                case_file,
                output_path=output_path,
                packet_dir=packet_dir,
                standalone_slurm=standalone_slurm,
                validation_findings=findings,
                harness_result=PracticalHarnessResult(packet_dir, [], [], []),
                shell_check=subprocess.CompletedProcess(["bash", "-n"], 1, "", "not run"),
                packet_status="SKIPPED (validation errors)",
                repo_root=repo_root,
            ),
            encoding="utf-8",
        )
        print(f"Wrote no-run report with validation errors: {output_path}")
        return 1

    tasks = parse_csv_ints(args.tasks)
    memory_candidates = parse_csv_strings(args.memory_candidates)
    harness_result = write_practical_harness(
        data,
        case_file,
        output_dir=packet_dir,
        tasks=tasks,
        memory_candidates=memory_candidates,
    )
    standalone_slurm.parent.mkdir(parents=True, exist_ok=True)
    standalone_slurm.write_text(render_slurm(data, case_file), encoding="utf-8")
    shell_check = run_capture(
        [
            "bash",
            "-n",
            *[str(path) for path in harness_result.prep_scripts],
            *[str(path) for path in harness_result.scripts],
            str(standalone_slurm),
        ],
        cwd=repo_root,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_no_run_report(
            data,
            case_file,
            output_path=output_path,
            packet_dir=packet_dir,
            standalone_slurm=standalone_slurm,
            validation_findings=findings,
            harness_result=harness_result,
            shell_check=shell_check,
            packet_status="PASS",
            repo_root=repo_root,
        ),
        encoding="utf-8",
    )
    print(f"Wrote no-run report: {output_path}")
    print(f"  Gate 11 packet: {packet_dir}")
    print(f"  standalone Slurm render: {standalone_slurm}")
    return shell_check.returncode


def cmd_render_wps_field_proof(args: argparse.Namespace) -> int:
    case_file = Path(args.case_file)
    output_dir = Path(args.output_dir)
    data = load_case(case_file)
    repo_root = as_path(data["paths"]["wrf_src"])
    require_outside_repo(output_dir, repo_root, "WPS field-proof packet output")

    findings = validate_case(data, strict_files=False)
    add_wps_field_proof_findings(findings, data)
    errors = [finding for finding in findings if finding.severity == "ERROR"]
    if errors:
        print_findings(errors)
        return 1

    paths = write_wps_field_proof_packet(data, case_file, output_dir=output_dir)
    shell_check = run_capture(["bash", "-n", str(output_dir / "wps_field_proof.slurm")], cwd=repo_root)
    print(f"Wrote WPS field-proof packet: {output_dir}")
    for path in paths:
        print(f"  {path}")
    if shell_check.returncode != 0:
        sys.stderr.write(shell_check.stderr)
    return shell_check.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and render BRC WRF case manifests without running WRF."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="check a case manifest")
    validate.add_argument("case_file")
    validate.add_argument(
        "--strict-files",
        action="store_true",
        help="treat missing external files/directories as errors",
    )
    validate.set_defaults(func=cmd_validate)

    render = subparsers.add_parser(
        "render-slurm",
        help="render a Slurm script to stdout or --output; never submits",
    )
    render.add_argument("case_file")
    render.add_argument("--output", help="write rendered script to this path")
    render.set_defaults(func=cmd_render_slurm)

    practical = subparsers.add_parser(
        "render-practical-harness",
        help="render a Gate 11 review packet and benchmark Slurm scripts; never submits",
    )
    practical.add_argument("case_file")
    practical.add_argument(
        "--output-dir",
        required=True,
        help="write the packet outside the brc-wrf checkout, for example under /tmp",
    )
    practical.add_argument(
        "--tasks",
        default=",".join(str(value) for value in DEFAULT_PRACTICAL_TASKS),
        help="comma-separated scaling task counts to render",
    )
    practical.add_argument(
        "--memory-candidates",
        help="optional comma-separated memory requests to render as candidate scripts",
    )
    practical.set_defaults(func=cmd_render_practical_harness)

    wps_proof = subparsers.add_parser(
        "render-wps-field-proof",
        help="render an approval-gated WPS-only field proof packet; never submits",
    )
    wps_proof.add_argument("case_file")
    wps_proof.add_argument(
        "--output-dir",
        required=True,
        help="write the packet outside the brc-wrf checkout, preferably under the archive control root",
    )
    wps_proof.set_defaults(func=cmd_render_wps_field_proof)

    report = subparsers.add_parser(
        "render-no-run-report",
        help="write a login-safe metadata/render report; never reads artifacts or submits",
    )
    report.add_argument("case_file")
    report.add_argument(
        "--output",
        help="write the Markdown report outside the brc-wrf checkout; default is under /tmp",
    )
    report.add_argument(
        "--packet-dir",
        help="write the Gate 11 packet outside the brc-wrf checkout; default is beside the report",
    )
    report.add_argument(
        "--slurm-output",
        help="write standalone render-slurm output outside the brc-wrf checkout; default is beside the report",
    )
    report.add_argument(
        "--tasks",
        default=",".join(str(value) for value in DEFAULT_PRACTICAL_TASKS),
        help="comma-separated scaling task counts to render in the packet",
    )
    report.add_argument(
        "--memory-candidates",
        help="optional comma-separated memory requests to render as candidate scripts",
    )
    report.set_defaults(func=cmd_render_no_run_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
