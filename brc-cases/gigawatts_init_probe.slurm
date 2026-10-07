#!/bin/bash
# Initialization/three-step probe using free ranks, before the 56-rank measurements.
#SBATCH --account=lawson-np
#SBATCH --partition=lawson-np
#SBATCH --nodelist=notch392
#SBATCH --nodes=1
#SBATCH --ntasks=8
#SBATCH --mem=256G
#SBATCH --time=00:30:00
#SBATCH --job-name=gw_init_probe
set -euo pipefail
: "${GW_CONTROL:?}"
[[ "$SLURM_NTASKS" == 8 ]]
sha256sum -c "$GW_CONTROL/init_probe_tool.sha256"
sha256sum -c "$GW_CONTROL/runtime_source_sha256.txt"
PY="$HOME/software/pkg/miniforge3/envs/brc-tools-2026/bin/python"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1
export EVIDENCE="$GW_CONTROL/init_probe_$SLURM_JOB_ID"
export RUN="/scratch/general/vast/$USER/wrf_runs/gigawatts_600m/init_probe_$SLURM_JOB_ID"
mkdir "$RUN" "$EVIDENCE"
BUILD=$("$PY" -B -c 'import json,sys;print(json.load(open(sys.argv[1]))["build_directory"])' "$GW_CONTROL/build/build_manifest.json")
export BUILD
cd "$BUILD"
sha256sum -c "$GW_CONTROL/build/build_sha256.txt"
sha256sum -c "$GW_CONTROL/build/runtime_sha256.txt"
"$PY" -B - <<'PY'
import hashlib,json,os,shutil,sys
from pathlib import Path
c=Path(os.environ['GW_CONTROL']);run=Path(os.environ['RUN']);e=Path(os.environ['EVIDENCE']);build=Path(os.environ['BUILD'])
sys.path.insert(0,str(c));from conveyor_ctl import set_key
real=json.loads((c/'real_complete.json').read_text());audit=json.loads((c/'initial_fields_audit.json').read_text())
assert real['accepted'] and audit['accepted'] and audit['real_job']==real['job']
source=Path(real['run_dir'])
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(8*1024**2),b''):h.update(block)
    return h.hexdigest()
for line in (c/('real_'+real['job'])/'initial_sha256.txt').read_text().splitlines():
    digest,name=line.split(maxsplit=1);assert sha(source/name)==digest
for p in (build/'run').iterdir():
    if p.is_file() and not p.name.startswith('namelist') and p.name not in ('wrf.exe','real.exe','iofields.txt','tslist'):
        (run/p.name).symlink_to(p.resolve())
for name in ('wrfinput_d01','wrfinput_d02','wrfbdy_d01'):
    shutil.copy2(source/name,run/name);assert sha(source/name)==sha(run/name)
shutil.copy2(build/'main/wrf.exe',run/'wrf.exe')
for name in ('iofields.txt','tslist'):shutil.copy2(c/name,run/name)
text=(c/'namelist.base.input').read_text()
for key,value in {'run_hours':0,'run_minutes':0,'run_seconds':27,
                  'end_day':[26,26],'end_hour':[18,18],'end_minute':[0,0],'end_second':[27,27],
                  'output_diagnostics':0,'auxhist2_interval':[0,0],'auxhist3_interval':[0,0],
                  'auxhist4_interval':[0,0],'auxhist7_interval':[0,0]}.items():text=set_key(text,key,value)
text=set_key(text,'history_begin',[60,60],insert_group='time_control')
(run/'namelist.input').write_text(text);(e/'namelist.input').write_text(text)
(e/'preparation.json').write_text(json.dumps({'source_real':real,'run_dir':str(run),'simulated_seconds':27,
 'coarse_steps':3,'ranks':8,'history_suppressed':True,'purpose':'runtime initialization only; no performance, transport or stability acceptance'},indent=2)+'\n')
PY
module purge
module load intel-oneapi-compilers/2021.4.0 intel-oneapi-mpi/2021.1.1 hdf5/1.14.3 netcdf-c/4.9.2 netcdf-fortran/4.6.1
export NETCDF=$(nf-config --prefix) NETCDF_C=$(nc-config --prefix)
cd "$RUN"
T0=$(date +%s)
set +e
srun --mpi=pmi2 -n "$SLURM_NTASKS" ./wrf.exe
rc=$?
set -e
mkdir "$EVIDENCE/rsl"
cp rsl.* "$EVIDENCE/rsl/"
[[ "$rc" == 0 ]]
export ELAPSED="$(( $(date +%s)-T0 ))"
"$PY" -B - <<'PY'
import json,os,sys
from pathlib import Path
c=Path(os.environ['GW_CONTROL']);e=Path(os.environ['EVIDENCE']);run=Path(os.environ['RUN'])
sys.path.insert(0,str(c));from conveyor_ctl import scan_all_rsl,classify
r=scan_all_rsl(run,8)
assert classify(0,r,True,False)[0]=='ok',r
assert r['last_time']=='2025-01-26_18:00:27',r
p=json.loads((e/'preparation.json').read_text())
p.update(job=os.environ['SLURM_JOB_ID'],accepted_initialization=True,launch_wall_seconds=int(os.environ['ELAPSED']),all_rank_scan=r)
(e/'acceptance.json').write_text(json.dumps(p,indent=2)+'\n');(c/'init_probe_complete.json').write_text(json.dumps(p,indent=2)+'\n')
print('PASS: eight-rank initialization and three coarse steps; the 56-rank measurements and stability tests remain pending')
PY
