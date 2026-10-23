#!/usr/bin/env python3
"""Seal a fresh P2 control from accepted inputs; never submit or launch a model."""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

from prepare_delayed_static import prepare, sha
from prepare_gigawatts_front_static import namelist


def module(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def export_blobs(repo, revision, paths, target):
    """WRF export-ignore suppresses git archive: copy committed blobs explicitly."""
    entries=subprocess.check_output(['git','-C',str(repo),'ls-tree','-rz',revision,'--',*paths]).split(b'\0')
    for entry in entries:
        if not entry:continue
        meta,name=entry.split(b'\t',1);mode,kind,oid=meta.decode().split()
        assert kind=='blob' and mode in ('100644','100755'),(kind,mode,name)
        p=target/name.decode();p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(subprocess.check_output(['git','-C',str(repo),'cat-file','blob',oid]))
        p.chmod(0o755 if mode=='100755' else 0o644)


def seal(a):
    assert os.environ.get('SLURM_JOB_ID'),'strict preparation belongs on Slurm'
    assert math.isfinite(a.tracer_surcharge_max) and a.tracer_surcharge_max >= 0
    tracer_adv=[a.tracer_adv_opt]*2
    c,old=a.control.resolve(),a.previous_control.resolve()
    assert not c.exists(),'a new control directory is required'
    c.mkdir(parents=True);(c/'logs').mkdir();(c/'build').mkdir();(c/'sources').mkdir()
    def copy(source,dest):
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
    build_meta=json.loads((a.build_evidence/'build_manifest.json').read_text())
    assert build_meta['tracers']['active_scalars']==12
    assert build_meta['slurm']['state']=='COMPLETED' and build_meta['slurm']['exit_code']=='0:0', 'terminal compile proof required'
    assert 'result=PASS_COMPILE_ONLY' in (a.build_evidence/'job_summary.txt').read_text()
    assert 'exit_code=0' in (a.build_evidence/'job_summary.txt').read_text()
    build=Path(build_meta['build_directory'])
    for file in ('build_manifest.json','build_sha256.txt','runtime_sha256.txt'):
        copy(a.build_evidence/file,c/'build'/file)
    with (c/'logs/build_verification.txt').open('w') as log:
        for file in ('build_sha256.txt','runtime_sha256.txt'):
            subprocess.run(['sha256sum','-c',str(c/'build'/file)],cwd=build,stdout=log,check=True)
        subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('check_tracer_registry.py')),
                        str(build),'--generated','--count','12'],stdout=log,check=True)
    ub=c/'sources'/('ub-wx-'+a.ub_sha);wrf=c/'sources'/('brc-wrf-'+a.wrf_sha)
    rel='experiments/drainage-canyons-gigawatts'
    export_blobs(a.ub_source,a.ub_sha,[rel+'/handoff',rel+'/analysis',rel+'/data'],ub)
    export_blobs(a.wrf_source,a.wrf_sha,['brc-cases'],wrf)
    exp=ub/rel;tools=wrf/'brc-cases'
    brctools='brc-tools-49817aa143c154bea406d97f7cfafb4f7b973af5'
    assert (old/'sources'/brctools/'brc_tools').is_dir()
    (c/'sources'/brctools).symlink_to((old/'sources'/brctools).resolve())
    for file in ('real_complete.json','initial_fields_audit.json','wps_complete.json','tslist'):
        copy(old/file,c/file)
    real=json.loads((c/'real_complete.json').read_text());source=Path(real['run_dir'])
    audit=json.loads((c/'initial_fields_audit.json').read_text())
    assert real['accepted'] and audit['accepted'] and audit['real_job']==real['job']
    realdir='real_'+real['job']
    copy(old/realdir/'initial_sha256.txt',c/realdir/'initial_sha256.txt')
    with (c/'logs/initial_verification.txt').open('w') as log:
        subprocess.run(['sha256sum','-c',str(c/realdir/'initial_sha256.txt')],cwd=source,stdout=log,check=True)
    from netCDF4 import Dataset
    reuse={}
    for domain in (1,2):
        with Dataset(source/f'wrfinput_d{domain:02d}') as nc:
            names={n for n in nc.variables if n.startswith('tr17_')}
            assert {f'tr17_{n}' for n in range(1,13)} <= names
            reuse[f'd{domain:02d}']={'available_scalar_count':len(names),'active_package':12,
                'policy':'Reuse identical accepted initial fields; only compiled tr17_1..12 are advanced. New restart count is checked in the bounded suite.'}
    (c/'initial_reuse.json').write_text(json.dumps(reuse,indent=2)+'\n')
    for file in ('conveyor_ctl.py','wrf_conveyor.slurm','preflight_check.py','seed_tracers_gigawatts.py','wrf_levels.py','iofields.txt'):
        copy(exp/'handoff'/file,c/file)
    for file in ('prepare_gigawatts_smoke.py','check_namelist_registry.py','submit_p2_chain.py'):
        copy(tools/file,c/file)
    copy(exp/'analysis/iter7/check_transport.py',c/'check_transport.py')
    ctl=module('p2_controller',c/'conveyor_ctl.py')
    base=ctl.set_key((old/'namelist.base.input').read_text(),'tracer_adv_opt',tracer_adv)
    base=ctl.set_key(base,'bl_mynn_tkeadvect',[False,False])
    (c/'namelist.base.input').write_text(base)
    # The case manifest and rendered control agree on this distinct build.
    import yaml
    case=yaml.safe_load((tools/'gigawatts_600m.case.yaml').read_text())
    case['paths']['wrf_build']=str(build)
    case['paths']['wrf_src']=str(wrf)
    case['slurm']['mpi_launcher']='srun --kill-on-bad-exit=1 --mpi=pmi2'
    case['case']['label']='January drainage P2 reference: 3 km / 600 m, 12 scalars'
    (c/'gigawatts_600m.case.yaml').write_text(yaml.safe_dump(case,sort_keys=False))
    # Reuse the accepted real-derived static fields, changing only the reviewed
    # HGT blend and the new delayed namelist. No WPS/real rerun is needed.
    oldfront=json.loads((old/'front_static_complete.json').read_text())
    assert oldfront['accepted_static_packet']
    raw=Path(oldfront['source']);assert sha(raw)==oldfront['source_sha256']
    static=c/('front_static_'+os.environ['SLURM_JOB_ID']);static.mkdir()
    front=prepare(raw,static/'wrfinput_d03',build/'Registry','2025-01-26_19:15:00',
                  c/'iofields.txt',parent=source/'wrfinput_d02')
    (static/'namelist.delayed.input').write_text(namelist(base,ctl,delayed=True,tracer_adv_opt=tracer_adv))
    (static/'preparation.json').write_text(json.dumps({'source_real':str(source),
        'previous_static_packet':oldfront,'scope':'reuse accepted static source; apply B1 and E1'},indent=2)+'\n')
    for target in (c/'namelist.base.input',static/'namelist.delayed.input'):
        subprocess.run([sys.executable,'-B',str(c/'check_namelist_registry.py'),'--build',str(build),
            '--namelist',str(target),'--output',str(c/'logs'/(target.name+'.registry.json'))],check=True)
    front.update(job=os.environ['SLURM_JOB_ID'],control=str(static),accepted_static_packet=True,
        delayed_namelist_sha256=sha(static/'namelist.delayed.input'),
        landuse_normalization=oldfront.get('landuse_normalization'),previous_packet=oldfront['control'])
    (static/'acceptance.json').write_text(json.dumps(front,indent=2)+'\n')
    (c/'front_static_complete.json').write_text(json.dumps(front,indent=2)+'\n')
    review={'accepted_for_bounded_delayed_test':True,'static_job':front['job'],
        'static_sha256':front['output_sha256'],'namelist_sha256':front['delayed_namelist_sha256'],
        'basis':'22 October E1/B1 authorization; unchanged accepted static source; exact WRF SINT and 5+5 blend; registry validation',
        'gate':'200 m follow-on only; D1 excludes this test from the reference prerequisite'}
    (c/'front_static_review.json').write_text(json.dumps(review,indent=2)+'\n')
    (c/'delayed_model_tools').mkdir()
    for name in ('prepare_gigawatts_delayed.py','prepare_delayed_static.py','nest_terrain.py','gigawatts_delayed.slurm'):
        copy(tools/name,c/'delayed_model_tools'/name)
    (c/'delayed_model_tool.sha256').write_text(''.join(sha(p)+'  '+str(p)+'\n' for p in sorted((c/'delayed_model_tools').iterdir())))
    template=c/'reference_template';shutil.copytree(old/'flight1_readiness_20261007/reference_template',template)
    meta={'capsule_version':10,'previous_control':str(old),'GW_UB_SHA':a.ub_sha,'GW_WRF_SHA':a.wrf_sha,
        'GW_EXPERIMENT':str(exp),'GW_WRF_SOURCE':str(wrf),'build_source_commit':build_meta['source_commit'],
        'compiled_scalars':12,'tracer_adv_opt':tracer_adv,'tracer_surcharge_max':a.tracer_surcharge_max,
        'delayed_epssm':[.3,.3,.9],
        'terrain_blend':{'spec_bdy_width':5,'blend_width':5},'prepared_by_job':os.environ['SLURM_JOB_ID'],
        'reference_launch_authorized':False}
    (c/'source_capsule.json').write_text(json.dumps(meta,indent=2)+'\n')
    # Hash only small control/source files. Mutable run state and acceptance
    # results are outside this manifest; static NetCDF has its own pinned hash.
    files=[p for p in c.iterdir() if p.is_file()]
    files += [p for tree in (ub,wrf,c/'sources'/brctools,c/'delayed_model_tools',template,c/'build') for p in tree.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    (c/'runtime_source_sha256.txt').write_text(''.join(sha(p)+'  '+str(p)+'\n' for p in sorted(set(files))))
    (c/'source_capsule_complete.txt').write_text('PASS: immutable P2 sources, build and initial fields verified; bounded runs pending\n')
    print(json.dumps(meta,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('previous-control','control','build-evidence','wrf-source','ub-source'):
        p.add_argument('--'+name,type=Path,required=True)
    for name in ('wrf-sha','ub-sha'):p.add_argument('--'+name,required=True)
    p.add_argument('--tracer-adv-opt',type=int,choices=(1,2),default=2)
    p.add_argument('--tracer-surcharge-max',type=float,default=.40,
                   help='Explicitly authorized fractional integration surcharge limit')
    seal(p.parse_args())
