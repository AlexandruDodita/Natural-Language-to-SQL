#!/usr/bin/env bash
# Run the naive arm over BIRD-SQL dev for several hosted models at once.
#
#   ./benchmark/sweep_bird.sh                       # the three default models
#   ./benchmark/sweep_bird.sh gemini-3.6-flash      # or name your own
#   DATASET=bird_dev_dict ./benchmark/sweep_bird.sh gemini-3.7-flash
#                                   # the same run with BIRD's own column
#                                   # dictionary added to the schema prompt
#
# Parallel by model, sequential within a model. The arm is I/O-bound -- it waits
# on the API, not on this machine -- so three at a time costs nothing locally
# and turns three consecutive multi-hour runs into one. It is deliberately not
# parallel *within* a model: the per-question latency column is a measurement,
# and concurrent requests to one endpoint would be measuring the queue.
#
# Each model writes its own results file and its own log, so one model failing
# leaves the other two untouched.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
cd "$REPO"

MODELS=("$@")
if [ ${#MODELS[@]} -eq 0 ]; then
  # Chosen to span the field rather than to sample it evenly: the weakest
  # hosted model already separated by the second-wave questions, the strongest
  # flash model, and the pro model. The last two both score 100% on car_rental
  # and adventureworks, so they are the rows that say whether BIRD breaks the
  # ceiling this project's own question sets no longer reach.
  MODELS=(gemini-2.5-flash gemini-3.7-flash gemini-3.1-pro-preview)
fi

# The repo's .env names the key for the frontend. The benchmark reads
# GEMINI_API_KEY, so map it here rather than asking every caller to.
if [ -z "${GEMINI_API_KEY:-}" ] && [ -f .env ]; then
  GEMINI_API_KEY=$(grep -m1 '^VITE_GEMINI_API_KEY=' .env | cut -d= -f2- | tr -d '"'"'"'\r')
  export GEMINI_API_KEY
fi
[ -n "${GEMINI_API_KEY:-}" ] || { echo "GEMINI_API_KEY not set and not in .env" >&2; exit 1; }

# Which schema the prompt carries: bird_dev is plain DDL, bird_dev_dict adds
# BIRD's per-column descriptions. Same questions, same databases, same arm.
DATASET=${DATASET:-bird_dev}
QUESTIONS="$HERE/questions_bird_dev.json"
[ -f "$QUESTIONS" ] || { echo "missing $QUESTIONS; run benchmark_data/bird/prepare.py" >&2; exit 1; }
N=$(.venv/bin/python -c "import json;print(len(json.load(open('$QUESTIONS'))['questions']))")

LOG_DIR="$HERE/.sweep-logs"
OUT_DIR="$HERE/results/$DATASET"
mkdir -p "$LOG_DIR" "$OUT_DIR"

echo "BIRD-SQL dev [$DATASET]: $N questions x ${#MODELS[@]} models, started $(date -Is)"

# Tracked by pid, never by pattern: pkill -f on a python command line also
# matches the shell that typed it, and a sweep that kills its own driver loses
# every model it has not started yet.
PIDS=()
for m in "${MODELS[@]}"; do
  log="$LOG_DIR/$DATASET-$m.log"
  GEMINI_MODEL="$m" nohup .venv/bin/python benchmark/run.py \
      --arm naive --dataset "$DATASET" \
      --out "$OUT_DIR/naive-$m.json" > "$log" 2>&1 &
  PIDS+=($!)
  echo "  started $m  pid=${PIDS[-1]}  log=${log#$REPO/}"
done

trap 'echo "interrupted; stopping ${PIDS[*]}"; kill "${PIDS[@]}" 2>/dev/null' INT TERM

fail=0
for i in "${!PIDS[@]}"; do
  if wait "${PIDS[$i]}"; then
    echo "=== ${MODELS[$i]} finished $(date -Is)"
  else
    echo "=== ${MODELS[$i]} FAILED (exit $?) -- see $LOG_DIR/$DATASET-${MODELS[$i]}.log"
    fail=1
  fi
  tail -14 "$LOG_DIR/$DATASET-${MODELS[$i]}.log" | sed 's/^/    /'
done

echo "sweep done $(date -Is)"
exit $fail
