#!/bin/bash
# Bounded initial-condition stage. Submit only after the WPS packet is accepted.
# No wrf.exe integration occurs here. Eight ranks fit the currently free portion of notch392;
# the timed WRF comparisons retain their separate 56-rank configuration.
#SBATCH --account=lawson-np
#SBATCH --partition=lawson-np
#SBATCH --nodelist=notch392
#SBATCH --nodes=1
#SBATCH --ntasks=8
#SBATCH --mem=256G
#SBATCH --time=01:00:00
#SBATCH --job-name=gw_real
set -euo pipefail
: "${GW_CONTROL:?durable control directory required}"
: "${GW_WPS_DIR:?accepted WPS output directory required}"
: "${GW_EXPERIMENT:?experiment source directory required}"
test -s "$GW_CONTROL/audit_complete.txt"
test -s "$GW_CONTROL/staging_complete.txt"
PY="$HOME/software/pkg/miniforge3/envs/brc-tools-2026/bin/python"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1
export PYTHONPATH="$GW_CONTROL/sources/brc-tools-49817aa143c154bea406d97f7cfafb4f7b973af5:$GW_EXPERIMENT/analysis/iter5"
RUN="/scratch/general/vast/$USER/wrf_runs/gigawatts_600m/real_$SLURM_JOB_ID"
mkdir "$RUN"
export RUN
BUILD=$("$PY" -B -c 'import json,sys;print(json.load(open(sys.argv[1]))["build_directory"])' "$GW_CONTROL/build/build_manifest.json")
export BUILD
cd "$BUILD"
sha256sum -c "$GW_CONTROL/build/build_sha256.txt" > "$GW_CONTROL/logs/real_${SLURM_JOB_ID}_build_check.txt"
sha256sum -c "$GW_CONTROL/build/runtime_sha256.txt" >> "$GW_CONTROL/logs/real_${SLURM_JOB_ID}_build_check.txt"
sha256sum -c "$GW_CONTROL/wps/wps_sha256.txt" > "$GW_CONTROL/logs/real_${SLURM_JOB_ID}_wps_check.txt"
"$PY" -B - <<'PY'
import os, pathlib, sys
sys.path.insert(0, os.environ['GW_CONTROL'])
from preflight_check import Report, check_metgrid_times
r=Report();check_metgrid_times(pathlib.Path(os.environ['GW_WPS_DIR']),r)
assert r.failed==0
run=pathlib.Path(os.environ['RUN']);build=pathlib.Path(os.environ['BUILD'])
for p in (build/'run').iterdir():
    if p.is_file() and not p.name.startswith('namelist') and p.name not in ('iofields.txt','tslist','wrf.exe','real.exe'):
        (run/p.name).symlink_to(p.resolve())
for p in pathlib.Path(os.environ['GW_WPS_DIR']).glob('met_em.d0*.nc'):
    (run/p.name).symlink_to(p.resolve())
PY
cp "$BUILD/main/real.exe" "$RUN/real.exe"
cp "$BUILD/main/wrf.exe" "$RUN/wrf.exe"
cp "$GW_CONTROL/namelist.base.input" "$RUN/namelist.input"
cp "$GW_CONTROL/iofields.txt" "$GW_CONTROL/tslist" "$RUN/"
"$PY" -B "$GW_CONTROL/check_namelist_registry.py" --build "$BUILD" --namelist "$RUN/namelist.input" --output "$GW_CONTROL/logs/real_${SLURM_JOB_ID}_namelist_groups.json"
"$PY" -B "$GW_EXPERIMENT/analysis/iter5/wrf_lake_twin_outline.py" prepare --state observed --state-table "$GW_EXPERIMENT/data/iter6/lake_ice_fraction_d02_20250126.csv" --window -111.50 -107.70 39.15 41.75 --met-em-dir "$GW_WPS_DIR" --pattern 'met_em.d0?.2025-01-26_18*' --out "$RUN/lake_edits" --write
for f in "$RUN/lake_edits"/met_em.d0*.nc; do ln -sfn "$f" "$RUN/$(basename "$f")"; done
"$PY" -B "$GW_CONTROL/preflight_check.py" metgrid --met-em-dir "$RUN" > "$GW_CONTROL/logs/real_${SLURM_JOB_ID}_metgrid_check.txt"
"$PY" -B "$GW_CONTROL/preflight_check.py" namelist --namelist "$RUN/namelist.input" --tslist "$RUN/tslist" --grid "$GW_WPS_DIR/geo_em.d02.nc" > "$GW_CONTROL/logs/real_${SLURM_JOB_ID}_namelist_check.txt"
module purge
module load intel-oneapi-compilers/2021.4.0 intel-oneapi-mpi/2021.1.1 hdf5/1.14.3 netcdf-c/4.9.2 netcdf-fortran/4.6.1
export NETCDF=$(nf-config --prefix) NETCDF_C=$(nc-config --prefix)
cd "$RUN"
T0=$(date +%s)
set +e
srun --mpi=pmi2 -n "$SLURM_NTASKS" ./real.exe
RC=$?
set -e
mkdir -p "$GW_CONTROL/real_$SLURM_JOB_ID"
cp rsl.* "$GW_CONTROL/real_$SLURM_JOB_ID/"
test "$RC" -eq 0
"$PY" -B - <<'PY'
import os,pathlib,sys
sys.path.insert(0,os.environ['GW_CONTROL'])
from conveyor_ctl import scan_all_rsl
run=pathlib.Path(os.environ['RUN'])
r=scan_all_rsl(run,int(os.environ['SLURM_NTASKS']))
assert not r['missing_ranks'] and not any(r.get(k) for k in ('cfl','nan','fatal')),r
text='\n'.join((run/name).read_text(errors='replace') for name in ('rsl.error.0000','rsl.out.0000') if (run/name).exists())
assert 'SUCCESS COMPLETE REAL_EM INIT' in text,'missing real.exe success marker'
PY
"$PY" -B "$GW_CONTROL/preflight_check.py" real --run-dir "$RUN" --lake-tool "$GW_EXPERIMENT/analysis/iter5/wrf_lake_twin_outline.py" --state-table "$GW_EXPERIMENT/data/iter6/lake_ice_fraction_d02_20250126.csv" --levels-tool "$GW_CONTROL/wrf_levels.py" > "$GW_CONTROL/logs/real_${SLURM_JOB_ID}_fields_check.txt"
sha256sum wrfinput_d01 wrfinput_d02 wrfbdy_d01 namelist.input > "$GW_CONTROL/real_$SLURM_JOB_ID/initial_sha256.txt"
printf '{"job":"%s","run_dir":"%s","elapsed_seconds":%s,"accepted":true}\n' "$SLURM_JOB_ID" "$RUN" "$(( $(date +%s)-T0 ))" > "$GW_CONTROL/real_complete.json"
echo "PASS: real.exe and all initial-field checks"
