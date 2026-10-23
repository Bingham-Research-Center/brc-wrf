#!/usr/bin/env python3
"""Collect bounded P2 evidence and optionally prepare a STOPped reference; no sbatch."""
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys


def collect(c, prepare_reference=True):
    def read(name):
        path=c/name
        return json.loads(path.read_text()) if path.is_file() else {}
    capsule=read('source_capsule.json')
    markers={k:read('smoke_'+k+'_complete.json') for k in ('baseline12','control0','transport_chain','delayed_front')}
    costs=read('smoke_comparison.json')
    transport={}
    if markers['transport_chain']:
        path=Path(markers['transport_chain']['control'])/'transport.json'
        transport=json.loads(path.read_text())
    matched=costs.get('tracers',{})
    limit=capsule.get('tracer_surcharge_max',costs.get('rules',{}).get('tracer_surcharge_max',.40))
    assert math.isfinite(limit) and limit >= 0, 'invalid sealed cost limit'
    surcharge=matched.get('integration_surcharge_fraction')
    within_cost_rule=surcharge is not None and math.isfinite(surcharge) and surcharge <= limit
    checks={'baseline12':bool(markers['baseline12'].get('accepted_plumbing')),
        'control0':bool(markers['control0'].get('accepted_plumbing')),
        'matched_notch392_cost':bool(within_cost_rule and matched.get('node')=='notch392'
                                   and matched.get('compiled_scalars')==12),
        'transport12':bool(markers['transport_chain'].get('accepted_plumbing') and transport.get('accepted')
                           and transport.get('scalar_count')==12),
        'supported_capsule':capsule.get('capsule_version') in (9,10)}
    result={'job':os.environ['SLURM_JOB_ID'],'checks':checks,'reference_preflight_passed':all(checks.values()),
        'delayed_front':bool(markers['delayed_front'].get('accepted_plumbing')),
        'delayed_gates':'200 m follow-on nests only (D1)', 'matched_cost':costs,
        'applied_cost_rule':{'tracer_surcharge_max':limit,'within_cost_rule':within_cost_rule,
            'source':'source_capsule.json' if 'tracer_surcharge_max' in capsule else 'smoke_comparison.json legacy default'},
        'storage_free_bytes':shutil.disk_usage(c).free,
        'reference_submitted':False,'reference_requires':'measured evidence and recovery/storage review, then JRL explicit go',
        'missing_evidence':[name for name,ok in checks.items() if not ok]}
    previous=read('p2_readiness.json')
    for key in ('prepared_reference','measured_daytime_wall_hours_per_sim_hour'):
        if key in previous:result[key]=previous[key]
    (c/'p2_readiness.json').write_text(json.dumps(result,indent=2)+'\n')
    if result['reference_preflight_passed'] and prepare_reference and 'prepared_reference' not in result:
        metric=read('smoke_baseline12_metrics.json')
        rate=metric['launch_wall_seconds']/metric['simulated_seconds']
        exp=Path(capsule['GW_EXPERIMENT'])
        args=[sys.executable,'-B',str(exp/'analysis/iter7/prepare_reference.py'),
            '--control',str(c),'--experiment',str(exp),'--template',str(c/'reference_template'),
            '--run-id','reference_p2_'+c.name,'--rate',str(rate),
            '--rate-source',f"P2 baseline12 {metric['job']} on notch392; daytime measured launch wall"]
        ref=Path(subprocess.check_output(args,text=True).strip())
        assert (ref/'STOP').is_file(),'reference preparation must retain STOP'
        result['prepared_reference']=str(ref)
        result['measured_daytime_wall_hours_per_sim_hour']=rate
        with (c/'reference_calendar.txt').open('w') as log:
            subprocess.run([sys.executable,'-B',str(ref/'conveyor_ctl.py'),'--control',str(ref),
                            'calendar','--rate',str(rate),'--smoke-rate',str(rate)],stdout=log,check=True)
        (c/'p2_readiness.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--control',type=Path,required=True)
    p.add_argument('--no-prepare-reference',action='store_true')
    a=p.parse_args();assert os.environ.get('SLURM_JOB_ID');collect(a.control,not a.no_prepare_reference)
