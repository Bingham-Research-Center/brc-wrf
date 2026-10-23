#!/bin/bash
# Additional guest test; never submits another job or writes official smoke metrics.
#SBATCH --account=owner-guest
#SBATCH --partition=notchpeak-guest
#SBATCH --nodes=1
#SBATCH --ntasks=32
#SBATCH --mem=160G
#SBATCH --time=02:00:00
#SBATCH --signal=B:USR1@300
#SBATCH --job-name=gw_guest_restart
set -euo pipefail
: "${GW_CONTROL:?}" "${GW_GUEST_PACKET:?}"
PY="$HOME/software/pkg/miniforge3/envs/brc-tools-2026/bin/python"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1
sha256sum -c "$GW_GUEST_PACKET/tools.sha256"
sha256sum -c "$GW_CONTROL/runtime_source_sha256.txt"
BUILD=$("$PY" -B -c 'import json,sys;print(json.load(open(sys.argv[1]))["build_directory"])' "$GW_CONTROL/build/build_manifest.json")
cd "$BUILD"
sha256sum -c "$GW_CONTROL/build/build_sha256.txt"
sha256sum -c "$GW_CONTROL/build/runtime_sha256.txt"
export CONVEYOR_DIR CONVEYOR_PYTHON="$PY" CONVEYOR_NO_RESUBMIT=1
export CONVEYOR_SRUN_ARGS=--kill-on-bad-exit=1
CONVEYOR_DIR=$("$PY" -B "$GW_GUEST_PACKET/gigawatts_guest_restart.py" setup --control "$GW_CONTROL")
printf '%s\n' "$CONVEYOR_DIR" > "$GW_GUEST_PACKET/control_${SLURM_JOB_ID}.txt"
forward_signal() {
  kill -s "$1" "$CONVEYOR_PID" 2>/dev/null || true
  wait "$CONVEYOR_PID" || true
  exit 1
}
trap 'forward_signal USR1' USR1
trap 'forward_signal TERM' TERM
bash "$CONVEYOR_DIR/wrf_conveyor.slurm" &
CONVEYOR_PID=$!
wait "$CONVEYOR_PID"
trap - USR1 TERM
"$PY" -B "$GW_GUEST_PACKET/gigawatts_guest_restart.py" finish --control "$CONVEYOR_DIR"
cp "$CONVEYOR_DIR/guest_acceptance.json" "$GW_GUEST_PACKET/acceptance_${SLURM_JOB_ID}.json"
