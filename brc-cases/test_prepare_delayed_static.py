import json

import numpy as np
from netCDF4 import Dataset, chartostring
import pytest

from prepare_delayed_static import REQUIRED, prepare, registry_inventory, sha


def packet(tmp_path):
    reg = tmp_path / 'Registry'
    reg.mkdir()
    (reg / 'Registry').write_text('include common\n')
    (reg / 'common').write_text('\n'.join(
        f'state real {n.lower()} ij misc 1 - i012rh "{n}" "static" ""'
        for n in sorted(REQUIRED)) + '\n')
    source = tmp_path / 'original.nc'
    with Dataset(source, 'w') as nc:
        for name, n in [('Time', 1), ('DateStrLen', 19), ('south_north', 2), ('west_east', 3)]:
            nc.createDimension(name, n)
        nc.setncatts({'GRID_ID': 3, 'START_DATE': '2025-01-26_18:00:00',
                     'SIMULATION_START_DATE': '2025-01-26_18:00:00'})
        nc.createVariable('Times', 'S1', ('Time', 'DateStrLen'))[:] = np.asarray(list('2025-01-26_18:00:00'), dtype='S1')[None, :]
        for n in sorted(REQUIRED | {'TSK', 'TSLB', 'SMOIS', 'SNOW', 'SNOWH', 'SEAICE', 'tr17_1', 'tr17_2'}):
            nc.createVariable(n, 'f4', ('Time', 'south_north', 'west_east'))[:] = 1.
    io = tmp_path / 'iofields.txt'
    io.write_text('# base\n\n+:h:7:tr17_1,tr17_2\n')
    return source, reg, io


def test_static_packet_preserves_source_and_excludes_transient_state(tmp_path):
    source, reg, io = packet(tmp_path)
    before = sha(source)
    output = tmp_path / 'wrfinput_d03'
    result = prepare(source, output, reg, '2025-01-26_19:15:00', io)
    assert sha(source) == before
    assert result['registry']['default_members'] == []
    assert not result['accepted_for_model_launch']
    with Dataset(output) as nc:
        assert set(nc.variables) == REQUIRED | {'Times'}
        assert list(chartostring(nc['Times'][:])) == ['2025-01-26_19:15:00']
        assert nc.SIMULATION_START_DATE == '2025-01-26_18:00:00'
        assert nc.START_DATE == '2025-01-26_19:15:00'
    text = output.with_suffix('.iofields.txt').read_text()
    assert '\n\n' not in text
    fields = text.split('+:i:6:')[1].strip().split(',')
    assert set(fields) == REQUIRED
    assert json.loads(output.with_suffix('.provenance.json').read_text())['source_sha256'] == before
    with pytest.raises(AssertionError, match='refusing to replace'):
        prepare(source, output, reg, '2025-01-26_19:15:00', io)


def test_occupied_stream_is_rejected_before_copy(tmp_path):
    source, reg, io = packet(tmp_path)
    with (reg / 'common').open('a') as f:
        f.write('state real tsk ij misc 1 - i06rh "TSK" "skin" "K"\n')
    with pytest.raises(AssertionError, match='already has fields'):
        prepare(source, tmp_path / 'output', reg, '2025-01-26_19:15:00', io)
    assert not (tmp_path / 'output').exists()


def test_base_input_mask_cannot_expand_the_allowlist(tmp_path):
    source, reg, io = packet(tmp_path)
    io.write_text('+:i:6:TSK\n')
    with pytest.raises(AssertionError, match='history rules only'):
        prepare(source, tmp_path / 'output', reg, '2025-01-26_19:15:00', io)


def test_registry_include_cycle_and_braced_stream_number(tmp_path):
    source, reg, io = packet(tmp_path)
    with (reg / 'common').open('a') as f:
        f.write('include Registry\nstate real x ij misc 1 - i{16}rh "X" "" ""\n')
    assert registry_inventory(reg)['default_members'] == []
    with (reg / 'common').open('a') as f:
        f.write('state real y ij misc 1 - i{6}rh "Y" "" ""\n')
    with pytest.raises(AssertionError, match='already has fields'):
        registry_inventory(reg)
