#!/bin/bash
# Derive a static d03 file and delayed-nest namelist; no model integration.
#SBATCH --account=lawson-np
#SBATCH --partition=lawson-np
#SBATCH --nodelist=notch392
#SBATCH --nodes=1
#SBATCH --ntasks=8
#SBATCH --mem=256G
#SBATCH --time=01:00:00
#SBATCH --job-name=gw_front_static
set -euo pipefail
: "${GW_CONTROL:?}"
[[ "$SLURM_NTASKS" == 8 ]]
sha256sum -c "$GW_CONTROL/front_static_tool.sha256"
sha256sum -c "$GW_CONTROL/runtime_source_sha256.txt"
sha256sum -c "$GW_CONTROL/wps/wps_sha256.txt"
PY="$HOME/software/pkg/miniforge3/envs/brc-tools-2026/bin/python"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1
export PYTHONPATH="$GW_CONTROL/front_static_tools"
BUILD=$("$PY" -B -c 'import json,sys;print(json.load(open(sys.argv[1]))["build_directory"])' "$GW_CONTROL/build/build_manifest.json")
cd "$BUILD"
sha256sum -c "$GW_CONTROL/build/build_sha256.txt"
sha256sum -c "$GW_CONTROL/build/runtime_sha256.txt"
export RUN
RUN=$("$PY" -B "$GW_CONTROL/front_static_tools/prepare_gigawatts_front_static.py" setup --control "$GW_CONTROL")
export EVIDENCE="$GW_CONTROL/front_static_$SLURM_JOB_ID"
module purge
module load intel-oneapi-compilers/2021.4.0 intel-oneapi-mpi/2021.1.1 hdf5/1.14.3 netcdf-c/4.9.2 netcdf-fortran/4.6.1
export NETCDF=$(nf-config --prefix) NETCDF_C=$(nc-config --prefix)
cd "$RUN/wps"
set +e
srun --mpi=pmi2 -n "$SLURM_NTASKS" ./metgrid.exe 2>&1 | tee "$EVIDENCE/metgrid_stdout.txt"
codes=("${PIPESTATUS[@]}")
set -e
cp metgrid.log* "$EVIDENCE/"
[[ "${codes[0]}" == 0 && "${codes[1]}" == 0 ]]
grep -q 'Successful completion of metgrid' "$EVIDENCE/metgrid_stdout.txt"
"$PY" -B - <<'PY'
import os,sys
from pathlib import Path
from netCDF4 import Dataset,chartostring
sys.path.insert(0,os.environ['GW_CONTROL'])
from preflight_check import canonical_time
run=Path(os.environ['RUN'])
files=sorted((run/'wps').glob('met_em.d03.*.nc'))
assert len(files)==2
seen=[]
for p in files:
    with Dataset(p) as nc:
        seen.extend(canonical_time(str(t)) for t in chartostring(nc['Times'][:]))
        assert len(nc.dimensions['num_metgrid_levels'])==51
        assert int(nc.getncattr('NUM_METGRID_SOIL_LEVELS'))==4
        assert {'TT','UU','VV','GHT','PSFC','SKINTEMP','SNOW','SNOWH'}<=set(nc.variables)
    (run/'real'/p.name).symlink_to(p)
assert seen==['2025-01-26_18:00:00','2025-01-26_19:00:00'],seen
PY
cd "$RUN/real"
set +e
srun --mpi=pmi2 -n "$SLURM_NTASKS" ./real.exe
rc=$?
set -e
mkdir "$EVIDENCE/real_logs"
cp rsl.* "$EVIDENCE/real_logs/"
[[ "$rc" == 0 ]]
"$PY" -B "$GW_CONTROL/front_static_tools/prepare_gigawatts_front_static.py" finish --control "$GW_CONTROL"
sha256sum "$EVIDENCE"/namelist.* "$EVIDENCE"/wrfinput_d03* > "$EVIDENCE/packet_sha256.txt"
echo 'PASS: static d03 packet and delayed namelist prepared. Actual model activation remains a separate test.'
