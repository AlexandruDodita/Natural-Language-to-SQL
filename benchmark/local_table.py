"""Render the local-model rows of the results table from the result files.

Written because transcribing eight models x two datasets by hand into
research.md is how a thesis ends up with a number that no file supports. Every
figure here is read back out of benchmark/results/, so the table cannot drift
from the runs that produced it.

    .venv/bin/python benchmark/local_table.py
"""

from __future__ import annotations

import collections
import json
import pathlib
import re
import statistics
import sys

RESULTS = pathlib.Path(__file__).resolve().parent / "results"

# Ordered small-to-large, which is also the order the sweep runs them in.
KEYS = ["arctic-7b-q4", "arctic-7b-q8", "qwen35-9b", "bonsai-27b-q1",
        "qwen36-27b-iq3", "qwen36-27b-q4", "qwen36-35b-moe"]

# The SQLite builtins a model trained on Spider/BIRD reaches for out of habit.
# Counting them separately is the difference between "this model cannot write
# the query" and "this model wrote the query in the wrong dialect".
SQLITE_ISMS = re.compile(
    r"\b(strftime|julianday|datetime\(|date\(|substr\(|ifnull|group_concat"
    r"|printf|instr|typeof|random\(\))", re.I)


def load(key: str, dataset: str) -> dict | None:
    p = RESULTS / f"local-{key}.json" if dataset == "car_rental" \
        else RESULTS / "adventureworks" / f"local-{key}.json"
    try:
        return json.loads(p.read_text())
    except FileNotFoundError:
        return None


def row(key: str, dataset: str) -> dict | None:
    d = load(key, dataset)
    if not d:
        return None
    rs = d["results"]
    # `truncated` was added to the arm at the same time as the 8,192-token
    # output budget. A file without it predates both, which means its "no SQL
    # produced" count silently includes replies the server cut off, and its
    # ambiguity column counts those as clarifications. Such a file is not
    # comparable with the rest of the table and is reported as stale rather
    # than quietly averaged in.
    if not any("truncated" in (r.get("extra") or {}) for r in rs):
        return {"key": key, "dataset": dataset, "stale": True}
    scored = [r for r in rs if r.get("scored")]
    correct = sum(1 for r in scored if r.get("correct"))
    dialect = sum(1 for r in rs if r.get("exec_error")
                  and SQLITE_ISMS.search(r["exec_error"]))
    exec_err = sum(1 for r in rs if r.get("exec_error"))
    trunc = sum(1 for r in rs if (r.get("extra") or {}).get("truncated"))
    nosql = sum(1 for r in rs if r.get("sql") is None)
    tps = [r["usage"]["decode_tokens_per_sec"] for r in rs
           if (r.get("usage") or {}).get("decode_tokens_per_sec")]
    lat = [r["latency_ms"] for r in rs if r.get("latency_ms")]
    return {
        "key": key, "dataset": dataset,
        "n": len(scored), "correct": correct,
        "acc": correct / len(scored) if scored else 0.0,
        "exec_err": exec_err, "dialect": dialect,
        # The upper bound the model would reach if every failure that is purely
        # a wrong-dialect builtin were rewritten. Not an accuracy figure and
        # must never be quoted as one -- it is the size of the dialect problem.
        "acc_ex_dialect": (correct + dialect) / len(scored) if scored else 0.0,
        "nosql": nosql, "truncated": trunc,
        "tps": statistics.median(tps) if tps else 0.0,
        "lat_s": statistics.median(lat) / 1000 if lat else 0.0,
    }


def main() -> int:
    for dataset in ("car_rental", "adventureworks"):
        rows = [r for k in KEYS if (r := row(k, dataset))]
        if not rows:
            continue
        print(f"\n### {dataset}\n")
        print("| model | acc | correct/n | exec err | of which dialect | "
              "ceiling if dialect fixed | no SQL | trunc | tok/s | med lat |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        stale = [r["key"] for r in rows if r.get("stale")]
        rows = [r for r in rows if not r.get("stale")]
        for r in sorted(rows, key=lambda x: -x["acc"]):
            print(f"| {r['key']} | {r['acc']*100:.1f}% | "
                  f"{r['correct']}/{r['n']} | {r['exec_err']} | {r['dialect']} | "
                  f"{r['acc_ex_dialect']*100:.1f}% | {r['nosql']} | "
                  f"{r['truncated']} | {r['tps']:.0f} | {r['lat_s']:.1f}s |")
        if stale:
            print(f"\nSTALE (pre-8192-budget, re-run needed): {', '.join(stale)}")
        missing = [k for k in KEYS
                   if not any(x["key"] == k for x in rows) and k not in stale]
        if missing:
            print(f"\nnot yet run: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
