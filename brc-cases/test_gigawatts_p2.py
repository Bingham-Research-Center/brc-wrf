import json
import subprocess

import pytest

from collect_gigawatts_p2 import collect
from prepare_gigawatts_smoke import tracer_advection
from submit_p2_chain import submit_chain


def write(root, name, value):
    (root / name).write_text(json.dumps(value))


@pytest.mark.parametrize('values', [[1, 1], [2, 2]])
def test_sealed_advection(tmp_path, values):
    write(tmp_path, 'source_capsule.json', {'tracer_adv_opt': values})
    assert tracer_advection(tmp_path) == values


def test_legacy_advection_default(tmp_path):
    assert tracer_advection(tmp_path) == [2, 2]
    write(tmp_path, 'source_capsule.json', {'capsule_version': 9})
    assert tracer_advection(tmp_path) == [2, 2]


@pytest.mark.parametrize('values', [[1, 2], [1], [3, 3]])
def test_invalid_advection_stops(tmp_path, values):
    write(tmp_path, 'source_capsule.json', {'tracer_adv_opt': values})
    with pytest.raises(AssertionError, match='unexpected sealed'):
        tracer_advection(tmp_path)


@pytest.mark.parametrize('version,limit,surcharge,node,transport,expected', [
    (9, None, .405, 'notch392', True, False),
    (9, None, .40, 'notch392', True, True),
    (10, .45, .405, 'notch392', True, True),
    (10, .45, .45, 'notch392', True, True),
    (10, .45, .45001, 'notch392', True, False),
    (10, .45, float('nan'), 'notch392', True, False),
    (10, .45, .40, 'notch384', True, False),
    (10, .45, .40, 'notch392', False, False),
    (11, .45, .40, 'notch392', True, False),
])
def test_collection_applies_sealed_cost_and_reference_gates(
        tmp_path, monkeypatch, version, limit, surcharge, node, transport, expected):
    monkeypatch.setenv('SLURM_JOB_ID', '123')
    capsule = {'capsule_version': version}
    if limit is not None:
        capsule['tracer_surcharge_max'] = limit
    write(tmp_path, 'source_capsule.json', capsule)
    for kind in ('baseline12', 'control0', 'transport_chain'):
        write(tmp_path, 'smoke_' + kind + '_complete.json',
              {'accepted_plumbing': True, 'control': str(tmp_path)})
    write(tmp_path, 'transport.json', {'accepted': transport, 'scalar_count': 12})
    costs = {'rules': {'tracer_surcharge_max': .40}, 'tracers': {
        'integration_surcharge_fraction': surcharge, 'within_cost_rule': surcharge <= .40,
        'node': node, 'compiled_scalars': 12}}
    write(tmp_path, 'smoke_comparison.json', costs)
    collect(tmp_path, prepare_reference=False)
    result = json.loads((tmp_path / 'p2_readiness.json').read_text())
    assert result['reference_preflight_passed'] is expected
    assert not result['delayed_front'] and not result['reference_submitted']
    assert result['applied_cost_rule']['tracer_surcharge_max'] == (limit or .40)
    assert json.loads((tmp_path / 'smoke_comparison.json').read_text())['rules'] == costs['rules']


@pytest.fixture
def sealed_control(tmp_path):
    (tmp_path / 'source_capsule_complete.txt').write_text('PASS')
    (tmp_path / 'brc-cases').mkdir()
    (tmp_path / 'brc-cases/gigawatts_p2_stage.slurm').touch()
    write(tmp_path, 'source_capsule.json', {
        'prepared_by_job': '100', 'GW_WRF_SOURCE': str(tmp_path), 'capsule_version': 10})
    return tmp_path


def test_bounded_submission_resources_dependencies_and_duplicate_guard(sealed_control, monkeypatch):
    commands = []

    def scheduler(cmd, **kwargs):
        if cmd[0] == 'sacct':
            return 'COMPLETED|0:0\n'
        commands.append(cmd)
        return str(100 + len(commands)) + '\n'

    monkeypatch.setattr(subprocess, 'check_output', scheduler)
    record = submit_chain(sealed_control)
    assert len(commands) == 6 and not record['reference_submission']
    deps = ['afterok:100', 'afterok:101', 'afterok:102', 'afterok:103',
            'afterany:101:102:103', 'afterany:104:105']
    for i, cmd in enumerate(commands):
        assert '--dependency=' + deps[i] in cmd
        assert not any(arg.startswith('--begin') for arg in cmd)
        if i < 4:
            for arg in ('--nodelist=notch392', '--ntasks=56', '--mem=900G', '--exclusive'):
                assert arg in cmd
        else:
            assert '--nodelist=notch137' in cmd and '--ntasks=1' in cmd
    with pytest.raises(AssertionError, match='already has'):
        submit_chain(sealed_control)
    assert len(commands) == 6


def test_partial_submission_is_preserved(sealed_control, monkeypatch):
    calls = []

    def scheduler(cmd, **kwargs):
        if cmd[0] == 'sacct':
            return 'COMPLETED|0:0\n'
        calls.append(cmd)
        if len(calls) == 2:
            raise subprocess.CalledProcessError(1, cmd)
        return '101\n'

    monkeypatch.setattr(subprocess, 'check_output', scheduler)
    with pytest.raises(subprocess.CalledProcessError):
        submit_chain(sealed_control)
    record = json.loads((sealed_control / 'submission.json').read_text())
    assert record['jobs'] == {'baseline12': '101'}
    assert 'control0' in record['commands']
    with pytest.raises(AssertionError, match='already has'):
        submit_chain(sealed_control)
