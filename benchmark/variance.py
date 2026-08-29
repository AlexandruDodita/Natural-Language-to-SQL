#!/usr/bin/env python3
"""Quantify run-to-run variance for one model on an unchanged setup.

Sampling noise is the first thing a results table has to survive. Repeating the
identical naive run on gemini-2.5-flash six times spans 3.8 points, so any
comparison in this chapter that turns on a smaller gap is reporting noise, not a
difference between systems. This script prints the numbers that claim rests on.

That spread was 11.5 points before the question set was disambiguated. Most of
what looked like sampling noise was the model re-guessing an under-specified
convention -- which payments count as revenue, which columns to project -- and
landing differently each time. Only q21 and q24 still move between runs.

    python benchmark/variance.py
"""
from __future__ import annotations

import glob, json, pathlib, statistics as st

HERE = pathlib.Path(__file__).resolve().parent
FILES = [HERE / "results" / "naive.json",
         HERE / "results" / "naive-gemini-2.5-flash.json"] + \
        [pathlib.Path(p) for p in sorted(glob.glob(str(HERE / "results" / "repeat" / "*.json")))]


def main() -> None:
    accs, per_q = [], {}
    for f in FILES:
        if not f.exists():
            continue
        d = json.loads(f.read_text())
        accs.append(d["summary"]["execution_accuracy"] * 100)
        for r in d["results"]:
            if r.get("scored"):
                per_q.setdefault(r["id"], []).append(bool(r["correct"]))
    accs.sort()
    unstable = sorted(q for q, v in per_q.items() if len(set(v)) > 1)
    out = {
        "model": "gemini-2.5-flash", "arm": "naive", "runs": len(accs),
        "accuracies": [round(a, 1) for a in accs],
        "mean": round(st.mean(accs), 1),
        "stdev": round(st.stdev(accs), 1) if len(accs) > 1 else None,
        "spread_points": round(max(accs) - min(accs), 1),
        "one_question_points": round(100 / len(per_q), 1),
        "unstable_questions": unstable,
        "always_correct": len([q for q, v in per_q.items() if all(v)]),
        "always_wrong": len([q for q, v in per_q.items() if not any(v)]),
    }
    (HERE / "results" / "variance.json").write_text(json.dumps(out, indent=2))
    for k, v in out.items():
        print(f"  {k:<22} {v}")
    print("\n  => differences smaller than roughly 2 standard deviations "
          f"({2 * (out['stdev'] or 0):.1f} points) are not distinguishable from noise.")


if __name__ == "__main__":
    main()
