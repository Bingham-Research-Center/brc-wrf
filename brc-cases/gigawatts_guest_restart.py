#!/usr/bin/env python3
"""Additional six-minute, two-launch guest test; never a production cost sample."""
import argparse
from collections import defaultdict
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys


def setup(root):
    capsule = json.loads((root / 'source_capsule.json').read_text())
    audit = json.loads((root / 'initial_fields_audit.json').read_text())
    real = json.loads((root / 'real_complete.json').read_text())
    assert audit['accepted'] and real['accepted'] and audit['real_job'] == real['job']
    target = Path(subprocess.check_output([sys.executable, '-B', str(root / 'prepare_gigawatts_smoke.py'),
        '--control', str(root), '--experiment', capsule['GW_EXPERIMENT'], '--kind', 'baseline24'], text=True).strip())
    # The existing preparer verifies and copies the accepted inputs. Only this new
    # per-job packet is shortened; official smoke controls and markers are untouched.
    blocks = (target / 'blocks.toml').read_text()
    replacements = {'name = "baseline24"': 'name = "guest_restart"',
        'sim_end = "2025-01-26_19:00:00"': 'sim_end = "2025-01-26_18:06:00"',
        'job_hours = 5': 'job_hours = 1.5', 'backstop_min = 60': 'backstop_min = 30',
        'restart_interval_min = 60': 'restart_interval_min = 3',
        'quantum_min = 15': 'quantum_min = 3',
        'history_interval = [60, 60]': 'history_interval = [3, 3]',
        'auxhist2_interval = [0, 20]': 'auxhist2_interval = [0, 3]',
        'auxhist7_interval = [0, 20]': 'auxhist7_interval = [0, 3]',
        'keep = ["2025-01-26_19:00:00"]': 'keep = ["2025-01-26_18:03:00"]'}
    for old, new in replacements.items():
        assert blocks.count(old) == 1, old
        blocks = blocks.replace(old, new)
    blocks += '\n[[rule]]\nname = "restart_proof"\nsim_from = "2025-01-26_18:03:00"\nsim_to = "2025-01-26_18:06:00"\n'
    (target / 'blocks.toml').write_text(blocks)
    state = json.loads((target / 'state.json').read_text())
    state['case'] = 'guest_restart'
    state['rate'] = {'smoke_wall_h_per_sim_h': 12.0,
        'source': 'conservative guest scheduling allowance only; not measured production performance'}
    (target / 'state.json').write_text(json.dumps(state, indent=2) + '\n')
    prep = json.loads((target / 'preparation.json').read_text())
    prep.update(kind='guest_restart', ranks=int(os.environ['SLURM_NTASKS']),
        node=os.environ.get('SLURM_JOB_NODELIST'), history_interval_minutes=3,
        scope='Two unseeded three-minute segments, 24 tracers; no production continuation or matched cost claim.')
    (target / 'preparation.json').write_text(json.dumps(prep, indent=2) + '\n')
    spec = importlib.util.spec_from_file_location('ctl', target / 'conveyor_ctl.py')
    ctl = importlib.util.module_from_spec(spec); spec.loader.exec_module(ctl)
    cfg = ctl.Config(target / 'blocks.toml')
    assert cfg.max_dom == 2 and cfg.quantum_min == cfg.restart_min == 3
    print(target)


def finish(target):
    from netCDF4 import Dataset, chartostring
    import numpy as np
    state = json.loads((target / 'state.json').read_text())
    assert state['status'] == 'complete' and len(state['segments']) == 2
    assert [(s['start'], s['end']) for s in state['segments']] == [
        ('2025-01-26_18:00:00', '2025-01-26_18:03:00'),
        ('2025-01-26_18:03:00', '2025-01-26_18:06:00')]
    assert all(s['outcome'] == 'ok' and not any(s['rsl'][k] for k in ('cfl', 'nan', 'fatal', 'missing_ranks')) for s in state['segments'])
    run = Path(state['wrf_run']); clocks = defaultdict(list); fields = []
    for d in (1, 2):
        for f in sorted(run.glob(f'wrfout_d{d:02d}_*')):
            with Dataset(f) as nc:
                clocks[str(d)].extend(str(t)[:11] + str(t)[11:].replace('_', ':') for t in chartostring(nc['Times'][:]))
                # Read a level at a time to bound memory; detect masked as well as nonfinite cells.
                for name in ('T', 'U', 'V', 'W', 'QVAPOR', 'T2', 'TSK', 'tr17_1', 'tr17_24'):
                    v = nc[name]
                    for k in range(v.shape[1] if v.ndim == 4 else 1):
                        a = v[0, k] if v.ndim == 4 else v[0]
                        assert not np.ma.getmaskarray(a).any() and np.isfinite(a).all(), (f, name, k)
                    fields.append({'file': f.name, 'field': name, 'finite_unmasked': True})
        assert clocks[str(d)] == [f'2025-01-26_18:{m:02d}:00' for m in (0, 3, 6)], clocks
    result = {'job': os.environ['SLURM_JOB_ID'], 'control': str(target), 'run_dir': str(run),
        'ranks': int(os.environ['SLURM_NTASKS']), 'node': os.environ['SLURM_JOB_NODELIST'],
        'accepted': True, 'simulated_seconds': 360, 'launches': 2, 'history_clocks': dict(clocks),
        'fields': fields, 'segments': state['segments'],
        'limits': 'Unseeded daytime startup/restart/output evidence; not tagged transport, nocturnal stability, budget closure, or notch392 cost.'}
    (target / 'guest_acceptance.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('fields', 'segments')}, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase', choices=('setup', 'finish'))
    p.add_argument('--control', type=Path, required=True)
    a = p.parse_args()
    assert os.environ.get('SLURM_JOB_ID'), 'This test belongs on Slurm'
    (setup if a.phase == 'setup' else finish)(a.control)
