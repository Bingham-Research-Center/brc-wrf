#!/usr/bin/env python3
"""Prepare/check the real-derived static d03 packet; never launch wrf.exe."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil

import numpy as np
from netCDF4 import Dataset, chartostring
from prepare_delayed_static import prepare, sha


def load_module(path):
    spec = importlib.util.spec_from_file_location('gw_controller', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# These settings are per-domain in the accepted two-domain control. Other
# two-value settings require explicit review rather than implicit extension.
EXTEND = set('frames_per_auxhist7 auxhist7_interval end_second end_minute '
    'start_second start_minute start_year start_month start_day start_hour '
    'end_year end_month end_day end_hour history_interval auxhist2_interval '
    'frames_per_auxhist2 auxhist4_interval frames_per_auxhist4 iofields_filename '
    'e_we e_sn e_vert dx dy grid_id parent_id i_parent_start j_parent_start '
    'parent_grid_ratio parent_time_step_ratio bl_mynn_tkeadvect tke_budget '
    'mp_physics sf_sfclay_physics bl_pbl_physics sf_surface_physics sf_lake_physics '
    'diff_6th_thresh diff_6th_slopeopt tracer_pblmix tracer_adv_opt tracer_opt'.split())


def namelist(base, ctl, delayed=False):
    text = base
    for match in list(re.finditer(r'^\s*([a-zA-Z0-9_]+)\s*=([^!\n]+)', base, re.M)):
        key, raw = match.groups()
        values = [s.strip() for s in raw.rstrip().rstrip(',').split(',')]
        if len(values) == 2:
            assert key in EXTEND, f'unreviewed two-value namelist key {key}'
            text = ctl.set_key(text, key, values + [values[-1]])
    values = {'max_dom': 3, 'run_days': 0, 'run_hours': 1, 'run_minutes': 0,
        'run_seconds': 0, 'end_day': [26]*3, 'end_hour': [19]*3,
        'e_we': [227,546,235], 'e_sn': [256,486,235], 'e_vert': [100]*3,
        'dx': [3000,600,200], 'dy': [3000,600,200], 'grid_id': [1,2,3],
        'parent_id': [1,1,2], 'i_parent_start': [1,71,237],
        'j_parent_start': [1,81,216], 'parent_grid_ratio': [1,5,3],
        'parent_time_step_ratio': [1,3,5], 'time_step': 9, 'feedback': 0,
        'restart': False, 'tracer_opt': [2]*3, 'bl_mynn_tkeadvect': [False]*3}
    if delayed:
        values.update(run_hours=1, run_minutes=15, restart=True,
            start_hour=[19]*3, start_minute=[0,0,15], end_hour=[20]*3,
            end_minute=[15]*3, history_interval=[15]*3,
            write_hist_at_0h_rst=True, ignore_iofields_warning=False,
            iofields_filename=['"iofields.txt"','"iofields.txt"','"wrfinput_d03.iofields.txt"'])
    for key, value in values.items():
        text = ctl.set_key(text, key, value)
    if delayed:
        for key, value in {'fine_input_stream':[0,0,6], 'io_form_auxinput2':2,
                           'io_form_auxinput6':2}.items():
            text = ctl.set_key(text, key, value, insert_group='time_control')
    return text


def paths(control):
    accepted=json.loads((control/'real_complete.json').read_text())
    audit=json.loads((control/'initial_fields_audit.json').read_text())
    assert accepted['accepted'] and audit['accepted']
    assert audit['real_job']==accepted['job']
    source=Path(accepted['run_dir'])
    wps=Path(json.loads((control/'wps_complete.json').read_text())['wps_dir'])
    build=Path(json.loads((control/'build/build_manifest.json').read_text())['build_directory'])
    evidence=control/('front_static_'+os.environ['SLURM_JOB_ID'])
    run=source.parent/('front_static_'+os.environ['SLURM_JOB_ID'])
    front=control.parents[2]/'gigawatts_iter5/gw5_front_200/domain_review/geogrid_20261006T054110Z_16068932'
    return source,wps,build,evidence,run,front


def setup(control):
    source,wps,build,e,run,front=paths(control)
    e.mkdir();run.mkdir();(run/'wps').mkdir();(run/'real').mkdir()
    ctl=load_module(control/'conveyor_ctl.py')
    geometry={}
    for dom in (1,2):
        name=f'geo_em.d{dom:02d}.nc'
        with Dataset(wps/name) as reference, Dataset(front/name) as candidate:
            fields=['XLAT_M','XLONG_M','HGT_M','LANDMASK','LU_INDEX','MAPFAC_M']
            for field in fields:
                np.testing.assert_array_equal(reference[field][:],candidate[field][:],err_msg=name+':'+field)
        geometry[name]={'accepted_sha256':sha(wps/name),'front_sha256':sha(front/name),'equal_fields':fields}
    with Dataset(front/'geo_em.d03.nc') as nc:
        assert (len(nc.dimensions['west_east']),len(nc.dimensions['south_north']))==(234,234)
        assert (nc.getncattr('DX'),nc.getncattr('DY'))==(200.,200.)
        assert (int(nc.getncattr('i_parent_start')),int(nc.getncattr('j_parent_start')))==(237,216)
    nml=(front/'namelist.wps').read_text()
    for key,value in {'start_date':["'2025-01-26_18:00:00'"]*3,
                      'end_date':["'2025-01-26_19:00:00'"]*3,
                      'fg_name':["'HRRR'","'GFSSOIL'"]}.items():
        nml=ctl.set_key(nml,key,value)
    nml=ctl.set_key(nml,'active_grid',[False,False,True],insert_group='share')
    (run/'wps/namelist.wps').write_text(nml)
    for name in ('metgrid','metgrid.exe'):
        (run/'wps'/name).symlink_to(build.parent/'WPS'/name)
    for p in front.glob('geo_em.d0*.nc'):
        (run/'wps'/p.name).symlink_to(p)
    forcing={}
    for stamp in ('2025-01-26_18','2025-01-26_19'):
        for prefix in ('HRRR','GFSSOIL'):
            p=wps/(prefix+':'+stamp)
            assert p.is_file(),p
            (run/'wps'/p.name).symlink_to(p.resolve())
            forcing[str(p.resolve())]=sha(p)
        for dom in (1,2):
            matches=list(source.glob(f'met_em.d{dom:02d}.{stamp}*.nc'))
            assert len(matches)==1,matches
            (run/'real'/matches[0].name).symlink_to(matches[0].resolve())
    for p in (build/'run').iterdir():
        if p.is_file() and not p.name.startswith('namelist') and p.name not in ('real.exe','wrf.exe','iofields.txt','tslist'):
            (run/'real'/p.name).symlink_to(p.resolve())
    shutil.copy2(build/'main/real.exe',run/'real/real.exe')
    shutil.copy2(control/'iofields.txt',run/'real/iofields.txt')
    base=(source/'namelist.input').read_text()
    (run/'real/namelist.input').write_text(namelist(base,ctl))
    (e/'namelist.delayed.input').write_text(namelist(base,ctl,delayed=True))
    shutil.copy2(run/'wps/namelist.wps',e/'namelist.wps')
    shutil.copy2(run/'real/namelist.input',e/'namelist.static_real.input')
    (e/'preparation.json').write_text(json.dumps({'source_real':str(source),'source_wps':str(wps),
        'front_geogrid':str(front),'parent_geometry':geometry,'forcing_sha256':forcing,
        'run_dir':str(run),'purpose':'derive static fields only; no WRF integration'},indent=2)+'\n')
    print(run)


def finish(control):
    source,wps,build,e,run,front=paths(control)
    ctl=load_module(control/'conveyor_ctl.py')
    scan=ctl.scan_all_rsl(run/'real',int(os.environ['SLURM_NTASKS']))
    assert not scan['missing_ranks'] and not any(scan.get(k) for k in ('cfl','nan','fatal')),scan
    assert 'SUCCESS COMPLETE REAL_EM INIT' in (run/'real/rsl.out.0000').read_text()
    with Dataset(run/'real/wrfinput_d03') as nc:
        assert (len(nc.dimensions['west_east']),len(nc.dimensions['south_north']))==(234,234)
        assert (int(nc.getncattr('GRID_ID')),int(nc.getncattr('PARENT_ID')))==(3,2)
        clocks=list(map(str,chartostring(nc['Times'][:])))
        assert clocks in [['2025-01-26_18:00:00'],['2025-01-26_18_00_00']],clocks
        with Dataset(run/'wps/geo_em.d03.nc') as geo:
            for wrf_name,geo_name in [('HGT','HGT_M'),('XLAT','XLAT_M'),('XLONG','XLONG_M'),('LU_INDEX','LU_INDEX')]:
                np.testing.assert_allclose(nc[wrf_name][:],geo[geo_name][:],rtol=0,atol=1e-5,err_msg=wrf_name)
    result=prepare(run/'real/wrfinput_d03',e/'wrfinput_d03',build/'Registry',
                   '2025-01-26_19:15:00',control/'iofields.txt')
    result.update(job=os.environ['SLURM_JOB_ID'],control=str(e),accepted_static_packet=True,
        delayed_namelist_sha256=sha(e/'namelist.delayed.input'),
        remaining='Copy accepted seeded parent restarts; run and inspect delayed d03 activation, inheritance and surface continuity.')
    (e/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
    (control/'front_static_complete.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage',choices=('setup','finish'))
    p.add_argument('--control',type=Path,required=True)
    a=p.parse_args()
    assert os.environ.get('SLURM_JOB_ID'),'NetCDF inspection belongs on Slurm'
    (setup if a.stage=='setup' else finish)(a.control)

if __name__=='__main__':
    main()
