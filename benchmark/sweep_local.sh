#!/usr/bin/env bash
# Run every local model against every dataset, unattended.
#
#   ./benchmark/sweep_local.sh [key ...]     # default: all seven, small first
#
# One model at a time, because 12 GiB of VRAM will not hold two. The sequence
# per model is: start llama-server, wait for it to answer /health, run the
# question set against each dataset, stop the server, wait for the port. The
# waiting is the whole reason this is a script rather than a shell loop typed by
# hand -- a 22 GiB MoE with two thirds of its experts on the CPU can take
# minutes to become ready, and a run started before then records a connection
# error as a wrong answer.
#
# Models are ordered small-to-large so a harness fault shows up in the two
# minutes the 7B takes rather than the hour the 35B takes.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(dirname "$HERE")"
PY="$REPO/.venv/bin/python"
LOG_DIR="${SWEEP_LOG_DIR:-$REPO/benchmark/.sweep-logs}"
mkdir -p "$LOG_DIR"

# A single SELECT does not need anything like this, but a reasoning-tuned model
# spends most of its budget deriving one before it writes it. At 4096
# Qwen3.5-9B was cut off on 6 of 44 car_rental questions -- 13.6 points of
# "wrong" that were nothing but a cap. 8192 still fits the largest prompt here
# (AdventureWorks, 6,967 tokens) inside the 16,384 context, so this costs no
# VRAM; it only costs time on the questions that use it.
export LOCAL_MAX_TOKENS="${LOCAL_MAX_TOKENS:-8192}"
export LOCAL_TIMEOUT_S="${LOCAL_TIMEOUT_S:-900}"

ALL=(arctic-7b-q4 arctic-7b-q8 qwen35-9b bonsai-27b-q1 \
     qwen36-27b-iq3 qwen36-27b-q4 qwen36-35b-moe)
if [ $# -gt 0 ]; then KEYS=("$@"); else KEYS=("${ALL[@]}"); fi

DATASETS=(car_rental adventureworks)

# The server is stopped by the pid this script started, never by pattern:
# pkill -f "llama-server" also matches the shell that typed that command, and
# a sweep that kills its own driver mid-run loses every model after the first.
SERVER_PID=""
stop_server() {
  [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null
  for _ in $(seq 1 60); do
    curl -sf http://127.0.0.1:1234/health >/dev/null 2>&1 || { SERVER_PID=""; return 0; }
    sleep 2
  done
  [ -n "$SERVER_PID" ] && kill -9 "$SERVER_PID" 2>/dev/null
  sleep 3
  SERVER_PID=""
}
trap 'stop_server' EXIT INT TERM

for key in "${KEYS[@]}"; do
  echo "=============================================================="
  echo "### $key  ($(date -Is))"
  stop_server
  nohup "$HERE/serve_local.sh" "$key" > "$LOG_DIR/serve-$key.log" 2>&1 &
  SERVER_PID=$!
  # 20 minutes: a Q4 27B loading from a cold page cache onto a half-CPU split
  # is genuinely slow the first time, and giving up early wastes the whole slot.
  ready=""
  for i in $(seq 1 400); do
    if curl -sf http://127.0.0.1:1234/health >/dev/null 2>&1; then ready=$i; break; fi
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
      echo "  server died while loading; see $LOG_DIR/serve-$key.log" >&2
      break
    fi
    sleep 3
  done
  if [ -z "$ready" ]; then
    echo "  SKIP $key: never became ready" >&2
    tail -5 "$LOG_DIR/serve-$key.log" >&2
    continue
  fi
  echo "  ready after $((ready * 3))s; $(nvidia-smi --query-gpu=memory.used \
       --format=csv,noheader 2>/dev/null) VRAM"

  for ds in "${DATASETS[@]}"; do
    out="$REPO/benchmark/results/local-$key.json"
    [ "$ds" = adventureworks ] && out="$REPO/benchmark/results/adventureworks/local-$key.json"
    echo "  --- $ds -> $(basename "$out")  ($(date -Is))"
    "$PY" "$HERE/run.py" --arm local --dataset "$ds" --local-model "$key" \
        --out "$out" > "$LOG_DIR/run-$key-$ds.log" 2>&1
    rc=$?
    if [ $rc -ne 0 ]; then
      echo "  FAILED rc=$rc; tail:" >&2
      tail -12 "$LOG_DIR/run-$key-$ds.log" >&2
    else
      grep -E "execution accuracy|tokens/s mean|invalid SQL|no SQL produced" \
        "$LOG_DIR/run-$key-$ds.log" | sed 's/^/      /'
    fi
  done
done

stop_server
echo "### sweep done ($(date -Is))"
