#!/bin/bash
# Finish a timed-out d02 metgrid pass from preserved intermediates, with overlap proof.
#SBATCH --account=lawson-np
#SBATCH --partition=lawson-np
#SBATCH --nodelist=notch392
#SBATCH --nodes=1
#SBATCH --ntasks=8
#SBATCH --mem=120G
#SBATCH --time=01:30:00
#SBATCH --job-name=gw_met_resume
set -euo pipefail
: "${GW_CONTROL:?}"
: "${GW_PREVIOUS_WPS_JOB:?}"
[[ "$GW_PREVIOUS_WPS_JOB" =~ ^[0-9]+$ ]]
[[ "$SLURM_NTASKS" == 8 ]]
if [[ -s "$GW_CONTROL/wps_complete.json" ]]; then
  echo 'The preceding WPS job already passed; no continuation is needed.'
  exit 0
fi
previous_state=$(sacct -X -n -j "$GW_PREVIOUS_WPS_JOB" -o State | tr -d '[:space:]')
[[ "$previous_state" == TIMEOUT ]] || { echo "Refusing automatic continuation from $previous_state; inspect the preceding job."; exit 2; }
sha256sum -c "$GW_CONTROL/runtime_source_sha256.txt"
sha256sum -c "$GW_CONTROL/wps/wps_sha256.txt"
sha256sum -c "$GW_CONTROL/metgrid_resume_tool.sha256"
PY="$HOME/software/pkg/miniforge3/envs/brc-tools-2026/bin/python"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1
export RUN="/scratch/general/vast/$USER/wrf_runs/gigawatts_600m/wps_metgrid_resume_$SLURM_JOB_ID/wps_run"
export EVIDENCE="$GW_CONTROL/wps_resume_$SLURM_JOB_ID"
mkdir -p "$(dirname "$RUN")"
mkdir "$RUN" "$EVIDENCE"
"$PY" -B - <<'PY'
from datetime import datetime,timedelta
import hashlib,json,os,re,shutil
from pathlib import Path
c=Path(os.environ['GW_CONTROL']);run=Path(os.environ['RUN']);e=Path(os.environ['EVIDENCE'])
job=os.environ['GW_PREVIOUS_WPS_JOB']
roots=list(run.parents[1].glob('wps_field_proof_'+job+'_*/wps_run'))
assert len(roots)==1,roots
old=roots[0]
log=(c/'logs'/('wps_'+job+'.out')).read_text(errors='replace')
assert 'Processing domain 2 of 2' in log
times=re.findall(r'Processing (\d{4}-\d\d-\d\d_\d\d)',log.split('Processing domain 2 of 2')[-1])
assert times
initial=datetime(2025,1,26,18)
last_started=datetime.strptime(times[-1],'%Y-%m-%d_%H')
assert last_started>=initial+timedelta(hours=2),'insufficient completed d02 overlap evidence'
resume=last_started-timedelta(hours=1)
stamp=resume.strftime('%Y-%m-%d_%H:%M:%S')
# Last-started output might be partial. Recompute it and the preceding hour;
# that preceding hour is the independent overlap check. Nothing is overwritten.
text=(old/'namelist.wps').read_text()
text,n=re.subn(r'(?m)^\s*start_date\s*=.*$',f" start_date = '2025-01-26_18:00:00', '{stamp}',",text)
assert n==1
assert not re.search(r'(?m)^\s*active_grid\s*=',text)
text=text.replace('&share','&share\n active_grid = .false., .true.,',1)
(run/'namelist.wps').write_text(text)
shutil.copy2(run/'namelist.wps',e/'namelist.wps')
build=Path(json.loads((c/'build/build_manifest.json').read_text())['build_directory'])
wps=build.parent/'WPS'
(e/'metgrid_table_sha256.txt').write_text(hashlib.sha256((wps/'metgrid/METGRID.TBL').read_bytes()).hexdigest()+'  '+str(wps/'metgrid/METGRID.TBL')+'\n')
for name in ('metgrid','metgrid.exe'):
    (run/name).symlink_to(wps/name)
for p in old.glob('geo_em.d0*.nc'):
    (run/p.name).symlink_to(p)
for pattern in ('HRRR:*','GFSSOIL:*'):
    for p in old.glob(pattern):
        (run/p.name).symlink_to(p)
for p in old.glob('met_em.d0*.nc'):
    date=p.name.split('.',2)[2][:-3];date=date[:11]+date[11:].replace('_',':')
    t=datetime.strptime(date,'%Y-%m-%d_%H:%M:%S')
    if p.name.startswith('met_em.d01.') or t<resume:
        (run/p.name).symlink_to(p)
meta={'previous_job':job,'previous_dir':str(old),'last_started':times[-1],
      'resume_time':stamp,'run_dir':str(run),'metgrid_ranks':8,
      'reason':'TIMEOUT only; reuse completed files and intermediates; independently recompute one completed overlap hour'}
(e/'preparation.json').write_text(json.dumps(meta,indent=2)+'\n')
with (e/'intermediate_sha256.txt').open('w') as f:
    for p in sorted(run.glob('*:*')):
        t=datetime.strptime(p.name.split(':',1)[1],'%Y-%m-%d_%H')
        if t<resume:continue
        h=hashlib.sha256()
        with p.open('rb') as data:
            for block in iter(lambda:data.read(8*1024**2),b''):h.update(block)
        f.write(h.hexdigest()+'  '+str(p.resolve())+'\n')
print(json.dumps(meta,indent=2))
PY
module purge
module load intel-oneapi-compilers/2021.4.0 intel-oneapi-mpi/2021.1.1 hdf5/1.14.3 netcdf-c/4.9.2 netcdf-fortran/4.6.1
export NETCDF=$(nf-config --prefix) NETCDF_C=$(nc-config --prefix)
cd "$RUN"
set +e
srun --mpi=pmi2 -n "$SLURM_NTASKS" ./metgrid.exe 2>&1 | tee "$EVIDENCE/metgrid_stdout.txt"
codes=("${PIPESTATUS[@]}")
set -e
cp metgrid.log* "$EVIDENCE/"
[[ "${codes[0]}" == 0 && "${codes[1]}" == 0 ]]
grep -q 'Successful completion of metgrid' "$EVIDENCE/metgrid_stdout.txt"
sha256sum -c "$EVIDENCE/metgrid_table_sha256.txt"
"$PY" -B - <<'PY'
import json,os,re,sys
from pathlib import Path
import numpy as np
from netCDF4 import Dataset
c=Path(os.environ['GW_CONTROL']);e=Path(os.environ['EVIDENCE']);run=Path(os.environ['RUN'])
sys.path.insert(0,str(c))
from preflight_check import Report,check_metgrid_times,canonical_time
meta=json.loads((e/'preparation.json').read_text());old=Path(meta['previous_dir'])
overlaps=list(run.glob('met_em.d02.'+meta['resume_time'].replace(':','_')+'.nc'))
assert len(overlaps)==1
proof={}
with Dataset(old/overlaps[0].name) as before,Dataset(overlaps[0]) as after:
    assert set(before.variables)==set(after.variables)
    for name in before.variables:
        x,y=before[name][:],after[name][:]
        assert x.shape==y.shape and np.array_equal(np.ma.getmaskarray(x),np.ma.getmaskarray(y)),name
        if x.dtype.kind in 'fiu':
            assert np.isfinite(x.compressed()).all() and np.isfinite(y.compressed()).all(),name
            np.testing.assert_allclose(x,y,rtol=2e-6,atol=1e-6,equal_nan=True,err_msg=name)
            delta=np.ma.abs(x.astype('f8')-y.astype('f8'))
            proof[name]=float(delta.max()) if delta.count() else None
        else:
            assert np.array_equal(x,y),name
(e/'overlap_field_differences.json').write_text(json.dumps(proof,indent=2)+'\n')
r=Report();check_metgrid_times(run,r);assert r.failed==0
for file in sorted(run.glob('met_em.d0*.nc')):
    with Dataset(file) as nc:
        assert len(nc.dimensions['num_metgrid_levels'])==51
        assert int(nc.getncattr('NUM_METGRID_SOIL_LEVELS'))==4
        fields=set(nc.variables)
        for pattern in (r'^(GHT|HGT)$',r'^(PRES|PRESSURE)$',r'^TT$',r'^(RH|QVAPOR|SPECHUMD)$',
                        r'^UU$',r'^VV$',r'^PSFC$',r'^PMSL$',r'^(LANDSEA|LANDMASK)$',
                        r'^(SOILHGT|HGT_M)$',r'^(ST|ST[0-9].*|SOILT[0-9].*)$',
                        r'^(SM|SM[0-9].*|SOILM[0-9].*)$',r'^SNOW$',r'^SNOWH$',r'^SKINTEMP$'):
            assert any(re.fullmatch(pattern,n) for n in fields),(file,pattern)
meta.update(job=os.environ['SLURM_JOB_ID'],wps_dir=str(run),hourly_times=49,met_em_count=98,
            overlap_fields_checked=len(proof),overlap_max_absolute_difference=max(v for v in proof.values() if v is not None))
(e/'acceptance.json').write_text(json.dumps(meta,indent=2)+'\n')
(c/'wps_complete.json').write_text(json.dumps(meta,indent=2)+'\n')
print('PASS: metgrid continuation, all 98 clocks/field groups/levels and independent overlap')
PY
