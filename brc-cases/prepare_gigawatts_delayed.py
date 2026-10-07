#!/usr/bin/env python3
"""Bounded delayed-nest restart test; no production continuation or pruning."""
import argparse
from datetime import datetime,timedelta
import importlib.util
import json
import os
from pathlib import Path
import shutil

import numpy as np
from netCDF4 import Dataset,chartostring
from prepare_delayed_static import sha


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def one(root,pattern):
    files=list(root.glob(pattern));assert len(files)==1,(root,pattern,files)
    return files[0]


def setup(c):
    real=json.loads((c/'real_complete.json').read_text())
    audit=json.loads((c/'initial_fields_audit.json').read_text())
    front=json.loads((c/'front_static_complete.json').read_text())
    chain=json.loads((c/'smoke_transport_chain_complete.json').read_text())
    assert real['accepted'] and audit['accepted'] and audit['real_job']==real['job']
    assert front['accepted_static_packet'] and chain['accepted_plumbing']
    static=Path(front['control']);parent=Path(chain['run_dir'])
    review=json.loads((c/'front_static_review.json').read_text())
    assert review['accepted_for_bounded_delayed_test']
    assert review['static_job']==front['job'] and review['static_sha256']==front['output_sha256']
    assert review['namelist_sha256']==front['delayed_namelist_sha256']
    assert json.loads((static/'preparation.json').read_text())['source_real']==real['run_dir']
    assert json.loads((Path(chain['control'])/'preparation.json').read_text())['source_real']['job']==real['job']
    assert json.loads((Path(chain['control'])/'transport.json').read_text())['accepted']
    build=Path(json.loads((c/'build/build_manifest.json').read_text())['build_directory'])
    e=c/('delayed_front_'+os.environ['SLURM_JOB_ID']);e.mkdir()
    run=Path(real['run_dir']).parent/e.name;run.mkdir()
    assert shutil.disk_usage(run).free>=200*1024**3,'less than 200 GiB scratch free'
    for p in (build/'run').iterdir():
        if p.is_file() and not p.name.startswith('namelist') and p.name not in ('wrf.exe','real.exe','iofields.txt','tslist'):
            (run/p.name).symlink_to(p.resolve())
    copies={}
    for dom in (1,2):
        p=one(parent,f'wrfrst_d{dom:02d}_2025-01-26_19*00*00')
        before=sha(p);shutil.copy2(p,run/p.name)
        assert sha(p)==sha(run/p.name)==before
        copies[p.name]={'source':str(p),'sha256':before}
    p=static/'wrfinput_d03'
    assert sha(p)==front['output_sha256']
    shutil.copy2(p,run/p.name)
    p=static/'wrfinput_d03.iofields.txt'
    assert sha(p)==front['iofields_sha256']
    shutil.copy2(p,run/p.name)
    p=static/'namelist.delayed.input'
    assert sha(p)==front['delayed_namelist_sha256']
    shutil.copy2(p,run/'namelist.input');shutil.copy2(p,e/'namelist.input')
    for name in ('iofields.txt','tslist'):
        shutil.copy2(c/name,run/name)
    shutil.copy2(build/'main/wrf.exe',run/'wrf.exe')
    boundary=Path(real['run_dir'])/'wrfbdy_d01'
    expected={line.split(maxsplit=1)[1]:line.split(maxsplit=1)[0]
        for line in (c/('real_'+real['job'])/'initial_sha256.txt').read_text().splitlines()}
    assert sha(boundary)==expected['wrfbdy_d01']
    shutil.copy2(boundary,run/boundary.name)
    assert sha(run/boundary.name)==expected['wrfbdy_d01']
    result={'run_dir':str(run),'control':str(e),'source_real':real,'static_packet':front,
        'source_transport':chain,'copied_parent_restarts':copies,'wrf_sha256':sha(run/'wrf.exe'),
        'start':'2025-01-26_19:00:00','activation':'2025-01-26_19:15:00','end':'2025-01-26_20:15:00',
        'launches':1,'production_continuation':False,
        'reason':'Keep activation strictly inside one launch. Generic conveyor splits at domain starts and is not used for this delayed test.'}
    (e/'preparation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(run)


def tracer_summary(nc,bounds):
    total=None;pairs=[]
    for k,(lo,hi) in enumerate(bounds):
        raw=[nc[f'tr17_{n}'][0] for n in (2*k+1,2*k+2)]
        assert not any(np.ma.getmaskarray(v).any() for v in raw),('masked tracer',k+1)
        c,ct=map(np.asarray,raw)
        assert np.isfinite(c).all() and np.isfinite(ct).all(),('nonfinite tracer',k+1)
        assert c.min()>=-1e-6 and c.max()<=1+1e-6 and ct.min()>=-5e-4,('tracer bounds',k+1)
        active=c>1e-6;ratio=ct[active]/c[active]
        assert not ratio.size or (ratio.min()>=lo-.05 and ratio.max()<=hi+.05),('theta ratio',k+1)
        assert not (~active).any() or np.abs(ct[~active]).max()<=1e-3,('untagged theta',k+1)
        if total is None:total=np.zeros(c.shape,dtype='f8')
        total+=c
        pairs.append({'pair':k+1,'active_cells':int(active.sum()),
                      'theta_min':float(ratio.min()) if ratio.size else None,
                      'theta_max':float(ratio.max()) if ratio.size else None})
    assert total.max()<=1+1e-5
    assert all(not np.ma.getmaskarray(nc[f'tr17_{n}'][:]).any() and np.all(nc[f'tr17_{n}'][:]==0) for n in (23,24)),'held pair changed'
    assert sum(p['active_cells'] for p in pairs)>0,'no inherited tags'
    return {'pairs':pairs,'sum_c_max':float(total.max()),'held_pair_zero':True}


def finish(c):
    ctl=module('delayed_ctl',c/'conveyor_ctl.py')
    clocks=module('delayed_clocks',c/'preflight_check.py')
    e=c/('delayed_front_'+os.environ['SLURM_JOB_ID'])
    prep=json.loads((e/'preparation.json').read_text());run=Path(prep['run_dir'])
    scan=ctl.scan_all_rsl(run,56)
    assert ctl.classify(0,scan,True,False)[0]=='ok',scan
    assert scan['last_time']==prep['end'],scan['last_time']
    bounds=[]
    for k in range(11):
        samples=[]
        for name in prep['copied_parent_restarts']:
            with Dataset(run/name) as nc:
                tag,theta=(np.asarray(nc[f'tr17_{n}'][0]) for n in (2*k+1,2*k+2))
                v=theta[tag>.5]/tag[tag>.5]
                if v.size:samples.append((float(v.min()),float(v.max())))
        assert samples,('unseeded source pair',k+1)
        bounds.append((min(v[0] for v in samples),max(v[1] for v in samples)))
    fields={};times={}
    for dom in (1,2,3):
        expected=[];t=datetime(2025,1,26,19,15 if dom==3 else 0)
        while t<=datetime(2025,1,26,20,15):
            expected.append(t.strftime('%Y-%m-%d_%H:%M:%S'));t+=timedelta(minutes=15)
        actual=[]
        for p in sorted(run.glob(f'wrfout_d{dom:02d}_*')):
            with Dataset(p) as nc:
                stamp=[clocks.canonical_time(str(v)) for v in chartostring(nc['Times'][:])]
                assert len(stamp)==1
                actual+=stamp
                for name in ('T','P','PB','PH','PHB','U','V','W','QVAPOR','TSK','TSLB','SMOIS','SNOW','SNOWH','SEAICE','HGT'):
                    values=nc[name][:]
                    assert not np.ma.getmaskarray(values).any() and np.isfinite(values).all(),(p.name,name)
                row={'tracers':tracer_summary(nc,bounds)}
                skin=np.asarray(nc['TSK'][:]);assert skin.min()>150 and skin.max()<350
                row['skin_range_K']=[float(skin.min()),float(skin.max())]
                fields[p.name]=row
        assert actual==expected,(dom,actual,expected)
        times[f'd{dom:02d}']=actual
    # Real terrain is retained in the interior; WRF may blend nest-edge terrain.
    with Dataset(e.parent/('front_static_'+prep['static_packet']['job'])/'wrfinput_d03') as static, Dataset(one(run,'wrfout_d03_2025-01-26_19*15*00')) as initial:
        terrain=np.asarray(initial['HGT'][0])-np.asarray(static['HGT'][0])
        assert np.abs(terrain[10:-10,10:-10]).max()<=1e-3,'interior static terrain changed'
        static_check={'terrain_max_difference_m':float(np.abs(terrain).max()),
                      'interior_max_difference_m':float(np.abs(terrain[10:-10,10:-10]).max())}
    # Quantify activation differences without treating bilinear parent sampling
    # as exact WRF terrain/land-mask interpolation or a science acceptance rule.
    from scipy.ndimage import map_coordinates
    continuity={}
    with Dataset(one(run,'wrfout_d02_2025-01-26_19*15*00')) as parent, Dataset(one(run,'wrfout_d03_2025-01-26_19*15*00')) as child:
        yy,xx=np.indices(child['HGT'].shape[1:]);x=236+(xx+.5)/3-.5;y=215+(yy+.5)/3-.5
        for name in ('TSK','SNOW','SNOWH','SEAICE','TSLB','SMOIS'):
            a=np.asarray(parent[name][0]);b=np.asarray(child[name][0])
            mapped=map_coordinates(a,[y,x],order=1,mode='nearest') if a.ndim==2 else np.asarray([map_coordinates(v,[y,x],order=1,mode='nearest') for v in a])
            diff=b-mapped
            continuity[name]={'mean_child_minus_parent':float(diff.mean()),'rms_difference':float(np.sqrt(np.mean(diff**2))),
                              'max_absolute_difference':float(np.abs(diff).max())}
    report={'job':os.environ['SLURM_JOB_ID'],'run_dir':str(run),'control':str(e),
        'accepted_plumbing':True,'all_rank_scan':scan,'output_times':times,'fields':fields,
        'static_check':static_check,'activation_surface_comparison':continuity,
        'limits':'Daytime activation and inherited tracer bounds only. Surface differences require review with changed terrain and land use. No nocturnal stability or science-run approval.'}
    (e/'acceptance.json').write_text(json.dumps(report,indent=2)+'\n')
    (c/'smoke_delayed_front_complete.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS: delayed clocks, static interior, inherited tags and all-rank logs; surface comparison saved for review')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=('setup','finish'))
    p.add_argument('--control',type=Path,required=True)
    a=p.parse_args();assert os.environ.get('SLURM_JOB_ID')
    setup(a.control) if a.stage=='setup' else finish(a.control)

if __name__=='__main__':main()
