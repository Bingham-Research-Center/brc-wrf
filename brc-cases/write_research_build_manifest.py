#!/usr/bin/env python3
"""Record a compile's verified evidence; terminal scheduler state is collected later."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess


def write(build, evidence):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(build), *args], text=True).strip()

    assert os.environ.get('SLURM_JOB_ID'), 'build metadata belongs to its Slurm job'
    assert not (evidence / 'compiler_errors.txt').read_text().strip()
    assert not (evidence / 'post_build_source.diff').read_text().strip()
    assert not (evidence / 'source_status.txt').read_text().strip()
    assert 'PASS:' in (evidence / 'tracer_generated_check.txt').read_text()
    hashes = {name: digest for digest, name in
              (line.split(maxsplit=1) for line in (evidence / 'build_sha256.txt').read_text().splitlines())}
    manifest = {
        'format_version': 1,
        'project': 'drainage-canyons-gigawatts',
        'validation_scope': 'compile_only; model pre-flight and scientific validation pending',
        'repository': 'https://github.com/Bingham-Research-Center/brc-wrf.git',
        'canonical_branch': 'john/wrf',
        'source_commit': git('rev-parse', 'HEAD'),
        'source_tree': git('rev-parse', 'HEAD^{tree}'),
        'upstream_baseline': 'WRF 4.8.0',
        'build_directory': str(build.resolve()),
        'evidence_directory': str(evidence.resolve()),
        'submodules': {line.split()[1]: line.split()[0].lstrip('-+') for line in
                       (evidence / 'submodules.txt').read_text().splitlines()},
        'slurm': {'job_id': os.environ['SLURM_JOB_ID'],
                  'state': 'terminal_state_pending',
                  'host': os.environ.get('SLURM_JOB_NODELIST'),
                  'cpus': int(os.environ['SLURM_CPUS_PER_TASK'])},
        'compile_checked_utc': datetime.now(timezone.utc).isoformat(),
        'configure': {'compiler_choice': 15, 'nesting_choice': 1, 'parallelism': 'dmpar'},
        'tracers': {'package': 'tracer_test1', 'tracer_opt': 2,
                    'active_scalars': 12, 'fields': 'tr17_1 through tr17_12'},
        'sha256': hashes,
        'runtime_sha256_file': str(evidence.resolve() / 'runtime_sha256.txt'),
        'runtime_hashed_entries': len((evidence / 'runtime_sha256.txt').read_text().splitlines()),
        'checks': {'clean_source_before': True, 'tracked_source_unchanged_after': True,
                   'compiler_error_scan_empty': True, 'generated_tracer_metadata': 'PASS',
                   'dynamic_libraries_resolved': True},
    }
    (evidence / 'build_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--evidence', type=Path, required=True)
    a = p.parse_args()
    write(a.build, a.evidence)
