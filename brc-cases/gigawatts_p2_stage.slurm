#!/bin/bash
# Sealed dispatch only; dependencies/resources are explicit sbatch arguments.
# Never submits a continuation or removes the reference STOP marker.
set -euo pipefail
: "${GW_CONTROL:?}"
PY="$HOME/software/pkg/miniforge3/envs/brc-tools-2026/bin/python"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1
test -s "$GW_CONTROL/source_capsule_complete.txt"
sha256sum -c --quiet "$GW_CONTROL/runtime_source_sha256.txt"
export GW_EXPERIMENT
GW_EXPERIMENT=$("$PY" -B -c 'import json,sys;print(json.load(open(sys.argv[1]))["GW_EXPERIMENT"])' "$GW_CONTROL/source_capsule.json")
GW_WRF_SOURCE=$("$PY" -B -c 'import json,sys;print(json.load(open(sys.argv[1]))["GW_WRF_SOURCE"])' "$GW_CONTROL/source_capsule.json")
case "${1:-}" in
  smoke) exec bash "$GW_WRF_SOURCE/brc-cases/gigawatts_smoke.slurm" ;;
  delayed) exec bash "$GW_WRF_SOURCE/brc-cases/gigawatts_delayed.slurm" ;;
  collect) exec "$PY" -B "$GW_WRF_SOURCE/brc-cases/collect_gigawatts_p2.py" --control "$GW_CONTROL" ;;
  collect-delayed) exec "$PY" -B "$GW_WRF_SOURCE/brc-cases/collect_gigawatts_p2.py" --control "$GW_CONTROL" --no-prepare-reference ;;
  *) echo 'Expected smoke, delayed or collect' >&2; exit 2 ;;
esac
