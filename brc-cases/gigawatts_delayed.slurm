#!/bin/bash
# One fixed 75-minute launch; delayed d03 activates strictly inside it.
#SBATCH --account=lawson-np
#SBATCH --partition=lawson-np
#SBATCH --nodelist=notch392
#SBATCH --nodes=1
#SBATCH --ntasks=56
#SBATCH --mem=900G
#SBATCH --time=08:00:00
#SBATCH --signal=B:USR1@300
#SBATCH --job-name=gw_delayed_front
set -euo pipefail
: "${GW_CONTROL:?}"
[[ "$SLURM_NTASKS" == 56 ]]
sha256sum -c "$GW_CONTROL/delayed_model_tool.sha256"
sha256sum -c "$GW_CONTROL/runtime_source_sha256.txt"
PY="$HOME/software/pkg/miniforge3/envs/brc-tools-2026/bin/python"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1
export PYTHONPATH="$GW_CONTROL/delayed_model_tools"
BUILD=$("$PY" -B -c 'import json,sys;print(json.load(open(sys.argv[1]))["build_directory"])' "$GW_CONTROL/build/build_manifest.json")
cd "$BUILD"
sha256sum -c "$GW_CONTROL/build/build_sha256.txt"
sha256sum -c "$GW_CONTROL/build/runtime_sha256.txt"
export RUN
RUN=$("$PY" -B "$GW_CONTROL/delayed_model_tools/prepare_gigawatts_delayed.py" setup --control "$GW_CONTROL")
EVIDENCE="$GW_CONTROL/delayed_front_$SLURM_JOB_ID"
"$PY" -B "$GW_CONTROL/preflight_check.py" seeded "$RUN"/wrfrst_d0?_2025-01-26_19* > "$EVIDENCE/seed_check.txt"
module purge
module load intel-oneapi-compilers/2021.4.0 intel-oneapi-mpi/2021.1.1 hdf5/1.14.3 netcdf-c/4.9.2 netcdf-fortran/4.6.1
export NETCDF=$(nf-config --prefix) NETCDF_C=$(nc-config --prefix)
cd "$RUN"
stop_test() {
  echo 'STOP: bounded delayed test interrupted; preserve every output and restart.' > "$EVIDENCE/STOP"
  mkdir -p "$EVIDENCE/rsl"
  cp rsl.* "$EVIDENCE/rsl/" 2>/dev/null || true
  exit 1
}
trap stop_test USR1 TERM
T0=$(date +%s)
set +e
srun --mpi=pmi2 -n "$SLURM_NTASKS" ./wrf.exe &
wait $!
rc=$?
set -e
trap - USR1 TERM
mkdir "$EVIDENCE/rsl"
cp rsl.* "$EVIDENCE/rsl/"
printf '%s\n' "$(( $(date +%s)-T0 ))" > "$EVIDENCE/launch_wall_seconds.txt"
[[ "$rc" == 0 ]]
"$PY" -B "$GW_CONTROL/delayed_model_tools/prepare_gigawatts_delayed.py" finish --control "$GW_CONTROL"
