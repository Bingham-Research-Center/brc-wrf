#!/bin/bash
# One bounded smoke only. No job dependencies or production continuation are created here.
#SBATCH --account=lawson-np
#SBATCH --partition=lawson-np
#SBATCH --nodelist=notch392
#SBATCH --nodes=1
#SBATCH --ntasks=56
#SBATCH --mem=900G
#SBATCH --time=06:00:00
#SBATCH --signal=B:USR1@300
#SBATCH --job-name=gw_smoke
set -euo pipefail
: "${GW_CONTROL:?durable control directory}"
: "${GW_EXPERIMENT:?experiment source directory}"
: "${GW_KIND:?baseline24, control0, tke24, or transport_chain}"
[[ "$SLURM_NTASKS" == 56 ]] || { echo 'comparison requires 56 ranks'; exit 2; }
PY="$HOME/software/pkg/miniforge3/envs/brc-tools-2026/bin/python"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1
export PYTHONPATH="$GW_CONTROL/sources/brc-tools-49817aa143c154bea406d97f7cfafb4f7b973af5"
BUILD=$("$PY" -B -c 'import json,sys;print(json.load(open(sys.argv[1]))["build_directory"])' "$GW_CONTROL/build/build_manifest.json")
cd "$BUILD"
sha256sum -c "$GW_CONTROL/build/build_sha256.txt" > "$GW_CONTROL/logs/smoke_${SLURM_JOB_ID}_build_check.txt"
sha256sum -c "$GW_CONTROL/build/runtime_sha256.txt" >> "$GW_CONTROL/logs/smoke_${SLURM_JOB_ID}_build_check.txt"
export CONVEYOR_DIR
CONVEYOR_DIR=$("$PY" -B "$GW_CONTROL/prepare_gigawatts_smoke.py" --control "$GW_CONTROL" --experiment "$GW_EXPERIMENT" --kind "$GW_KIND")
export CONVEYOR_PYTHON="$PY" CONVEYOR_NO_RESUBMIT=1
RUN=$("$PY" -B -c 'import json,sys;print(json.load(open(sys.argv[1]))["wrf_run"])' "$CONVEYOR_DIR/state.json")
if [[ "$GW_KIND" == transport_chain ]]; then
  LABELS="${GW_CONTROL%/gigawatts_600m/control/*}/terrain/labels"
  "$PY" -B "$GW_EXPERIMENT/handoff/seed_tracers_gigawatts.py" --labels "$LABELS/labels_green30.npz" --catchments "$LABELS/terrain_catchments_green30.csv" --sinks "$LABELS/terrain_sinks_green30.csv" "$RUN"/wrfrst_d0?_2025-01-26_19* > "$CONVEYOR_DIR/seeding.txt"
  "$PY" -B "$CONVEYOR_DIR/preflight_check.py" seeded "$RUN"/wrfrst_d0?_2025-01-26_19* > "$CONVEYOR_DIR/seed_check.txt"
  "$PY" -B "$CONVEYOR_DIR/conveyor_ctl.py" --control "$CONVEYOR_DIR" seeded --sim-time '2025-01-26_19:00:00'
fi
bash "$CONVEYOR_DIR/wrf_conveyor.slurm"
"$PY" -B "$GW_EXPERIMENT/analysis/iter7/check_smoke.py" --control "$CONVEYOR_DIR" --root "$GW_CONTROL" --kind "$GW_KIND"
if [[ "$GW_KIND" == transport_chain ]]; then
  "$PY" -B "$CONVEYOR_DIR/preflight_check.py" chain --control "$CONVEYOR_DIR" > "$CONVEYOR_DIR/chain_check.txt"
  "$PY" -B "$GW_EXPERIMENT/analysis/iter7/check_transport.py" --run-dir "$RUN" --output "$CONVEYOR_DIR/transport.json"
fi
# Completion is written only after every applicable check passes.
"$PY" -B - <<'PY'
import json,os,pathlib
c=pathlib.Path(os.environ['CONVEYOR_DIR']);s=json.loads((c/'state.json').read_text())
assert s['status']=='complete'
(pathlib.Path(os.environ['GW_CONTROL'])/('smoke_'+os.environ['GW_KIND']+'_complete.json')).write_text(json.dumps(
    {'job':os.environ['SLURM_JOB_ID'],'control':str(c),'run_dir':s['wrf_run'],'accepted_plumbing':True},indent=2)+'\n')
PY
