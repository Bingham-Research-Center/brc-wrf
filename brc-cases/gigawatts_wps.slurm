#!/bin/bash
# Consume the reviewed, complete single-cycle forcing contract; WPS only.
#SBATCH --account=lawson-np
#SBATCH --partition=lawson-np
#SBATCH --nodelist=notch392
#SBATCH --nodes=1
#SBATCH --ntasks=8
#SBATCH --mem=120G
#SBATCH --time=02:00:00
#SBATCH --job-name=gw_wps
set -euo pipefail
: "${GW_CONTROL:?durable control directory required}"
test -s "$GW_CONTROL/staging_complete.txt"
test -s "$GW_CONTROL/audit_complete.txt"
export PYTHONDONTWRITEBYTECODE=1
PY="$HOME/software/pkg/miniforge3/envs/brc-tools-2026/bin/python"
export PYTHONPATH="$GW_CONTROL/sources/brc-tools-11eccf1c6ee2d72cf6e79e54e60e962c0feaccbc"
"$PY" -B - <<'PY'
import collections, datetime as dt, json, os, pathlib
from brc_tools.nwp.wrf_staging import verify_manifest
root=pathlib.Path('/scratch/general/vast')/os.environ['USER']/'wrf_inputs/gigawatts_600m'
manifest=root/'manifest_gigawatts_600m.json'
m=json.loads(manifest.read_text()); c=json.loads((root/'contract_gigawatts_600m.json').read_text())
assert c['sources']==['hrrr','gfs_soil'] and c['wps_fg_name']==['HRRR','GFSSOIL']
assert c['interval_seconds']==3600
start=dt.datetime(2025,1,26,18,tzinfo=dt.timezone.utc)
rows=m['staged_files'];hrrr=[r for r in rows if r['source']=='hrrr'];soil=[r for r in rows if r['source']=='gfs_soil']
actual=collections.Counter((r['valid_time'],r['product']) for r in hrrr)
expected=collections.Counter({((start+dt.timedelta(hours=h)).strftime('%Y-%m-%dT%H:%M:%SZ'),p):1 for h in range(49) for p in ('nat','sfc')})
assert actual==expected
assert len(soil)==1 and soil[0]['valid_time']==start.strftime('%Y-%m-%dT%H:%M:%SZ')
report=verify_manifest(manifest);assert report['ok'] and report['n_files']==99, report
(pathlib.Path(os.environ['GW_CONTROL'])/'forcing/consumer_verification.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS: exact product/time coverage and 99 input hashes rechecked before WPS')
PY
sha256sum -c "$GW_CONTROL/wps/wps_sha256.txt"
export BRC_WPS_FIELD_PROOF_APPROVED=YES
bash "$GW_CONTROL/wps_packet/wps_field_proof.slurm"
# The renderer preserves all generated fields and logs under this unique job root.
"$PY" -B - <<'PY'
import json,os,pathlib,sys
control=pathlib.Path(os.environ['GW_CONTROL'])
root=pathlib.Path('/scratch/general/vast')/os.environ['USER']/'wrf_runs/gigawatts_600m'
dirs=list(root.glob('wps_field_proof_'+os.environ['SLURM_JOB_ID']+'_*/wps_run'))
assert len(dirs)==1,dirs
sys.path.insert(0,str(control))
from preflight_check import Report,check_metgrid_times
r=Report();check_metgrid_times(dirs[0],r);assert r.failed==0
(control/'wps_complete.json').write_text(json.dumps({'job':os.environ['SLURM_JOB_ID'],'wps_dir':str(dirs[0]),'hourly_times':49,'met_em_count':98},indent=2)+'\n')
PY
