#!/usr/bin/env python3
"""Render the October gigawatts control packet; text only, no model or submission.

Source WRF_ARCHIVE and BRC_WRF_ROOT from the experiment's .env before calling.
Geometry comes from domain_calc; all other values inherit the accepted archetype
with the declared October deltas. Generated artifacts go to durable control.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tomllib

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import domain_calc as dc
import wrf_case as wc


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--handoff', type=Path, required=True)
    p.add_argument('--control', type=Path, required=True)
    a = p.parse_args()
    control = a.control
    control.mkdir(parents=True, exist_ok=True)
    archive = Path(os.environ['WRF_ARCHIVE'])
    spec_path = HERE / 'specs/gigawatts_600m.domain.toml'
    spec = tomllib.loads(os.path.expandvars(spec_path.read_text()))
    grid = dc.build(spec)
    assert not grid.failed, dc.report(grid, spec)
    (control / 'domain_report.txt').write_text(dc.report(grid, spec))
    (control / 'namelist.wps').write_text(dc.namelist_geogrid(grid, spec))
    archetype = archive / 'green_river_600m/control/gateF_20260731T2158Z/namelist.input'
    # Remove stale historical comments, preserve all actual archetype settings.
    text = '\n'.join(line for line in archetype.read_text().splitlines() if line.strip() and not line.lstrip().startswith('!')) + '\n'
    mod_spec = importlib.util.spec_from_file_location('gigawatts_ctl', a.handoff / 'conveyor_ctl.py')
    cc = importlib.util.module_from_spec(mod_spec)
    mod_spec.loader.exec_module(cc)
    groups = {
      'time_control': {'run_days': 0, 'run_hours': 48, 'run_minutes': 0, 'run_seconds': 0,
        'start_year': [2025,2025], 'start_month': [1,1], 'start_day': [26,26], 'start_hour': [18,18], 'start_minute': [0,0], 'start_second': [0,0],
        'end_year': [2025,2025], 'end_month': [1,1], 'end_day': [28,28], 'end_hour': [18,18], 'end_minute': [0,0], 'end_second': [0,0],
        'restart': False, 'restart_interval': 60, 'override_restart_timers': True, 'write_hist_at_0h_rst': False,
        'history_interval': [60,60], 'auxhist2_interval': [0,20], 'auxhist4_interval': [0,1], 'auxhist7_interval': [0,20],
        'io_form_auxhist7': 2, 'frames_per_auxhist7': [1,1], 'iofields_filename': ['"iofields.txt"','"iofields.txt"']},
      'domains': {'max_ts_locs':128, 'max_ts_level':60},
      'physics': {'mp_physics':[8,8], 'tke_budget':[0,1], 'bl_mynn_tkeadvect':[False,False]},
      'dynamics': {'base_temp':268.0, 'tracer_opt':[2,2], 'tracer_adv_opt':[1,1], 'tracer_pblmix':[1,1],
                   'diff_6th_slopeopt':[0,1], 'diff_6th_thresh':[0.10,0.05]},
    }
    for group, settings in groups.items():
        for key, value in settings.items(): text = cc.set_key(text, key, value, insert_group=group)
    base = control / 'namelist.base.input'
    base.write_text('! Derived from the accepted Green River archetype and the October gigawatts deltas.\n' + text)
    dc.sync_namelist_input(grid, base)
    (control / 'namelist_deltas.json').write_text(json.dumps(groups, indent=2) + '\n')
    for name in ('iofields.txt','tslist','blocks.toml','state.example.json','conveyor_ctl.py','conveyor_status.py','wrf_conveyor.slurm','seed_tracers_gigawatts.py','preflight_check.py','wrf_levels.py'):
        shutil.copy2(a.handoff / name, control / name)
    vtables = control / 'vtables'
    vtables.mkdir(exist_ok=True)
    original = archive / 'green_river_600m/control/gateC_20260731T0253Z'
    shutil.copy2(original / 'Vtable.raphrrr.nosoil', vtables)
    soil = (original / 'Vtable.gfssoil').read_text()
    lines = [line for line in soil.splitlines() if not re.search(r'\|\s*(SKINTEMP|SNOW|SNOWH)\s*\|', line)]
    fields = {line.split('|')[4].strip() for line in lines if '|' in line and len(line.split('|')) > 5}
    assert not fields & {'SKINTEMP','SNOW','SNOWH'}
    assert {'SM000010','SM010040','SM040100','SM100200','ST000010','ST010040','ST040100','ST100200','LANDSEA'} <= fields
    (vtables / 'Vtable.gfssoil.only').write_text('\n'.join(lines) + '\n')
    case_file = HERE / 'gigawatts_600m.case.yaml'
    shutil.copy2(case_file, control)
    def expand(value):
        if isinstance(value, str): return os.path.expandvars(value)
        if isinstance(value, list): return [expand(v) for v in value]
        if isinstance(value, dict): return {k:expand(v) for k,v in value.items()}
        return value
    wc.write_wps_field_proof_packet(expand(wc.load_case(case_file)), case_file, output_dir=control / 'wps_packet')
    inputs = [archetype, spec_path, case_file, a.handoff / 'conveyor_ctl.py', original / 'Vtable.gfssoil']
    (control / 'render_input_sha256.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}, indent=2) + '\n')
    print(control)


if __name__ == '__main__': main()
