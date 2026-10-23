#!/usr/bin/env python3
"""Submit one bounded P2 chain from an explicit sealed control; no reference run."""
import argparse
import json
from pathlib import Path
import subprocess


def submit_chain(control):
    c = control.resolve()
    assert (c / 'source_capsule_complete.txt').is_file()
    assert not (c / 'submission.json').exists(), 'this control already has a submitted chain'
    capsule = json.loads((c / 'source_capsule.json').read_text())
    prepare_job = capsule['prepared_by_job']
    state = subprocess.check_output(['sacct', '-j', prepare_job, '-X', '--noheader',
                                     '--format=State,ExitCode', '-P'], text=True).strip()
    assert state == 'COMPLETED|0:0', state
    stage = Path(capsule['GW_WRF_SOURCE']) / 'brc-cases/gigawatts_p2_stage.slurm'
    assert stage.is_file()
    record = {'control': str(c), 'capsule': capsule, 'prepare_job': prepare_job,
              'jobs': {}, 'commands': {}, 'reference_submission': False}
    # Reserve the submission record before contacting Slurm. A partial or
    # uncertain submission needs reconciliation, never an automatic duplicate.
    with (c / 'submission.json').open('x') as handle:
        handle.write(json.dumps(record, indent=2) + '\n')

    def submit(name, mode, dependency, *, kind=None, model=False):
        cmd = ['sbatch', '--parsable', '--account=lawson-np', '--partition=lawson-np',
               '--nodes=1', '--kill-on-invalid-dep=yes', '--dependency=' + dependency,
               '--job-name=gw_p2_' + name, '--output=' + str(c / 'logs' / (name + '_%j.out')),
               '--error=' + str(c / 'logs' / (name + '_%j.err')),
               '--export=ALL,GW_CONTROL=' + str(c) + (',GW_KIND=' + kind if kind else '')]
        if model:
            cmd += ['--nodelist=notch392', '--ntasks=56', '--cpus-per-task=1', '--mem=900G',
                    '--exclusive', '--signal=B:USR1@300',
                    '--time=' + ('08:00:00' if mode == 'delayed' else '06:00:00')]
        else:
            cmd += ['--nodelist=notch137', '--ntasks=1', '--cpus-per-task=1', '--mem=16G',
                    '--time=00:30:00']
        cmd += [str(stage), mode]
        record['commands'][name] = cmd
        (c / 'submission.json').write_text(json.dumps(record, indent=2) + '\n')
        job = subprocess.check_output(cmd, text=True).strip()
        assert job.isdecimal(), job
        record['jobs'][name] = job
        (c / 'submission.json').write_text(json.dumps(record, indent=2) + '\n')
        print(name, job, flush=True)
        return job

    baseline = submit('baseline12', 'smoke', 'afterok:' + prepare_job, kind='baseline12', model=True)
    zero = submit('control0', 'smoke', 'afterok:' + baseline, kind='control0', model=True)
    transport = submit('transport', 'smoke', 'afterok:' + zero, kind='transport_chain', model=True)
    delayed = submit('delayed', 'delayed', 'afterok:' + transport, model=True)
    collector = submit('collect', 'collect', 'afterany:' + ':'.join((baseline, zero, transport)))
    submit('collect_delayed', 'collect-delayed', 'afterany:' + delayed + ':' + collector)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--control', type=Path, required=True)
    submit_chain(parser.parse_args().control)
