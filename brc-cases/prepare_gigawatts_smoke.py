#!/usr/bin/env python3
"""Prepare one bounded test from accepted gigawatts initial conditions, on Slurm."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--control', type=Path, required=True)
    p.add_argument('--experiment', type=Path, required=True)
    p.add_argument('--kind', choices=('baseline24', 'control0', 'tke24', 'transport_chain'), required=True)
    a = p.parse_args()
    assert os.environ.get('SLURM_JOB_ID'), 'file copies and hashes belong on Slurm'
    root = a.control
    accepted = json.loads((root / 'real_complete.json').read_text())
    assert accepted['accepted']
    source = Path(accepted['run_dir'])
    build = Path(json.loads((root / 'build/build_manifest.json').read_text())['build_directory'])
    target = root / 'smokes' / (a.kind + '_' + os.environ['SLURM_JOB_ID'])
    target.mkdir(parents=True, exist_ok=False)
    run = source.parent / target.name
    run.mkdir(exist_ok=False)
    if shutil.disk_usage(run).free < 200 * 1024**3:
        raise SystemExit('less than 200 GiB scratch free; review storage before the test')
    for line in (root / ('real_' + accepted['job']) / 'initial_sha256.txt').read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        assert sha(source / name) == digest, f'accepted initial file changed: {name}'
    for f in (build / 'run').iterdir():
        if f.is_file() and not f.name.startswith('namelist') and f.name not in ('iofields.txt', 'tslist', 'wrf.exe', 'real.exe'):
            (run / f.name).symlink_to(f.resolve())
    for name in ('wrfinput_d01', 'wrfinput_d02', 'wrfbdy_d01'):
        shutil.copy2(source / name, run / name)
    shutil.copy2(build / 'main/wrf.exe', run / 'wrf.exe')
    for name in ('iofields.txt', 'tslist'):
        shutil.copy2(root / name, run / name)
    for name in ('conveyor_ctl.py', 'wrf_conveyor.slurm', 'preflight_check.py'):
        shutil.copy2(a.experiment / 'handoff' / name, target / name)
    spec = importlib.util.spec_from_file_location('ctl', target / 'conveyor_ctl.py')
    cc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cc)
    base = (root / 'namelist.base.input').read_text()
    base = cc.set_key(base, 'tracer_opt', [0, 0] if a.kind == 'control0' else [2, 2])
    base = cc.set_key(base, 'bl_mynn_tkeadvect', [False, a.kind == 'tke24'])
    state = {'schema': 2, 'case': a.kind, 'wrf_run': str(run), 'status': 'idle', 'reason': '',
             'rate': {'smoke_wall_h_per_sim_h': 2.69, 'source': 'unmeasured prior sizing estimate'},
             'seeds_done': [], 'current': None, 'segments': []}
    end = '2025-01-26_19:00:00'
    history = 60
    rule = ''
    if a.kind == 'transport_chain':
        previous = json.loads((root / 'smoke_baseline24_complete.json').read_text())
        state = json.loads((Path(previous['control']) / 'state.json').read_text())
        assert state['status'] == 'complete' and len(state['segments']) == 1
        state.update(wrf_run=str(run), status='idle', current=None, seeds_done=[])
        for f in Path(previous['run_dir']).glob('wrfrst_d0?_2025-01-26_19*'):
            shutil.copy2(f, run / f.name)
        complete = cc.restart_sets(run).get(cc.parse(end), {})
        assert set(complete) == {1, 2}, 'baseline must have both 19Z restart files'
        end, history = '2025-01-26_19:30:00', 15
        # A rule boundary forces two distinct, naturally ending 15-minute launches.
        rule = '\n[[rule]]\nname = "second_restart"\nsim_from = "2025-01-26_19:15:00"\nsim_to = "2025-01-26_19:30:00"\n'
    (target / 'namelist.base.input').write_text(base)
    (target / 'blocks.toml').write_text(f'''[case]
name = "{a.kind}"
sim_start = "2025-01-26_18:00:00"
sim_end = "{end}"
max_dom = 2
time_step_s = 9.0
max_segments = 4
[window]
timezone = "America/Denver"
job_hours = 5
overrun_min = 0
backstop_min = 60
[sizing]
restart_interval_min = 60
quantum_min = 15
safety_bulk = 1.08
safety_topup = 1.03
startup_s = 300
[streams]
keys = ["history", "auxhist2", "auxhist3", "auxhist4", "auxhist7"]
[defaults]
override_restart_timers = ".true."
write_hist_at_0h_rst = ".false."
history_interval = [{history}, {history}]
auxhist3_interval = [60, 60]
auxhist2_interval = [0, 20]
auxhist4_interval = [0, 1]
auxhist7_interval = [0, 20]
[restarts]
keep_newest = 4
keep = ["2025-01-26_19:00:00"]
{rule}''')
    cc.Config(target / 'blocks.toml')
    (target / 'state.json').write_text(json.dumps(state, indent=2) + '\n')
    (target / 'preparation.json').write_text(json.dumps({'kind': a.kind, 'source_real': accepted,
        'wrf_sha256': sha(run / 'wrf.exe'), 'initial_sha256': {n: sha(run / n) for n in
        ('wrfinput_d01', 'wrfinput_d02', 'wrfbdy_d01')}, 'run_dir': str(run),
        'history_interval_minutes': history, 'production_continuation': False}, indent=2) + '\n')
    print(target)


if __name__ == '__main__':
    main()
