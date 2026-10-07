import os
from pathlib import Path
import re
import pytest
from prepare_gigawatts_front_static import namelist, load_module


def value(text,key):
    raw=re.search(r'^\s*'+key+r'\s*=([^!\n]+)',text,re.M)[1]
    return [s.strip() for s in raw.rstrip().rstrip(',').split(',')]


@pytest.fixture
def packet():
    c=Path(os.environ['GW_CONTROL'])
    return (c/'namelist.base.input').read_text(),load_module(c/'conveyor_ctl.py')


def test_delayed_clock_static_stream_and_matched_parents(packet):
    base,ctl=packet
    out=namelist(base,ctl,delayed=True)
    assert value(out,'start_hour')==['19']*3
    assert value(out,'start_minute')==['0','0','15']
    assert value(out,'end_hour')==['20']*3
    assert value(out,'end_minute')==['15']*3
    assert value(out,'fine_input_stream')==['0','0','6']
    assert value(out,'ignore_iofields_warning')==['.false.']
    assert value(out,'restart')==['.true.']
    for key in ['e_we','e_sn','e_vert','dx','dy','i_parent_start','j_parent_start',
                'parent_grid_ratio','parent_time_step_ratio','tracer_opt',
                'diff_6th_slopeopt','diff_6th_thresh','mp_physics','sf_surface_physics']:
        assert value(out,key)[:2]==value(base,key)[:2],key
    assert float(value(out,'time_step')[0])/3/5==.6


def test_real_packet_starts_all_three_domains_together(packet):
    base,ctl=packet
    out=namelist(base,ctl)
    assert value(out,'start_hour')==['18']*3
    assert value(out,'start_minute')==['0']*3
    assert value(out,'end_day')==['26']*3
    assert value(out,'end_hour')==['19']*3
    assert value(out,'restart')==['.false.']
    assert value(out,'e_we')[-1]=='235'
    assert value(out,'e_sn')[-1]=='235'


def test_unknown_two_value_setting_requires_review(packet):
    base,ctl=packet
    with pytest.raises(AssertionError,match='unreviewed'):
        namelist(base.replace('&physics','&physics\n unknown_setting = 1, 2,'),ctl)
