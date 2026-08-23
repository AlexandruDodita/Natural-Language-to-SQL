#!/usr/bin/env python3
"""Renders the results JSONs as the LaTeX table bodies used in the thesis.

    python benchmark/tables.py

Every number in the results chapter is printed by this script from the JSON the
harness wrote, so a table in the document can be regenerated from the measured
data instead of being retyped - and a typo in the thesis is a diff away from
being caught.
"""

from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
RESULTS = HERE / "results"
CATEGORIES = ["simple", "aggregate", "join", "subquery", "window"]


def load(name: str) -> dict | None:
    p = RESULTS / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def pct(x: float | None) -> str:
    return f"{x * 100:.1f}\\%" if x is not None else "--"


def num(x, d: int = 1) -> str:
    return f"{x:.{d}f}" if isinstance(x, (int, float)) else "--"


def tex_model(name: str, run: dict | None = None) -> str:
    """The model's name, plus the backend for a local run.

    A local throughput figure is meaningless without the engine that produced
    it, so the backend travels with the label rather than living in a footnote.
    """
    backend = (run or {}).get("backend") or ""
    for tag in ("CUDA", "Vulkan", "CPU"):
        if tag.lower() in backend.lower():
            # The file name may already carry the backend to keep two runs of
            # one model apart; the label should not say it twice.
            bare = name[: -len(tag) - 1] if name.lower().endswith("-" + tag.lower()) else name
            return "\\code{" + bare.replace("_", "\\_") + "}" + f" ({tag})"
    return "\\code{" + name.replace("_", "\\_") + "}"


def accuracy_rows(runs: list[tuple[str, dict]]) -> str:
    out = []
    for label, d in runs:
        s = d["summary"]
        cells = [pct(s["by_category"].get(c, {}).get("accuracy")) for c in CATEGORIES]
        amb = f"{s['ambiguous_clarified']}/{s['ambiguous_total']}"
        out.append(" & ".join([tex_model(label, d), *cells,
                               f"\\textbf{{{pct(s['execution_accuracy'])}}}", amb]) + " \\\\")
    return "\n".join(out)


def throughput_rows(runs: list[tuple[str, dict]]) -> str:
    out = []
    for label, d in runs:
        s = d["summary"]
        u = s.get("usage") or {}
        c = s.get("cost") or {}
        usd = c.get("usd_per_100_questions")
        out.append(" & ".join([
            tex_model(label, d),
            num(u.get("tokens_per_sec_mean"), 1),
            num(s.get("latency_ms_median", 0) / 1000 if s.get("latency_ms_median") else None, 2),
            str(int(u["prompt_tokens_mean"])) if u.get("prompt_tokens_mean") else "--",
            str(int(u["output_tokens_mean"])) if u.get("output_tokens_mean") else "--",
            f"{usd:.3f}" if isinstance(usd, (int, float)) else "--",
        ]) + " \\\\")
    return "\n".join(out)


def backend_note(runs: list[tuple[str, dict]]) -> str:
    """Everything a local number needs to be reproducible, and the decode rate."""
    out = []
    for label, d in runs:
        if d.get("arm") != "local":
            continue
        u = d["summary"].get("usage") or {}
        out.append(f"%   {label}: backend={d.get('backend')} "
                   f"end-to-end={u.get('tokens_per_sec_mean')} tok/s "
                   f"decode-only={u.get('decode_tokens_per_sec_mean')} tok/s "
                   f"TTFT median={u.get('ttft_ms_median')} ms "
                   f"n={d['summary'].get('n_scored')} scored")
    return "\n".join(out)


def report_rows(runs: list[tuple[str, dict]]) -> str:
    out = []
    for label, d in runs:
        s = d["summary"]
        out.append(" & ".join([
            tex_model(label),
            f"{s['chart_type_correct']}/{s['n']}",
            pct(s["chart_type_accuracy"]),
            pct(s.get("chart_type_accuracy_chartable")),
            pct(s.get("chart_type_accuracy_scalar")),
            pct(s["structural_validity"]),
        ]) + " \\\\")
    return "\n".join(out)


def main() -> None:
    names = sorted(p.stem for p in RESULTS.glob("*.json"))
    # Only the per-model files: `naive.json`, `pipeline.json` and
    # `mcp-postgres.json` are single-model arm runs and belong to the arm
    # comparison table, not to the model comparison table.
    sql_runs = [(n.replace("naive-", "").replace("local-", ""), load(n))
                for n in names if n.startswith(("naive-", "local-"))]
    sql_runs = [(lbl, d) for lbl, d in sql_runs if d]
    # Runs that exist only to isolate one variable - a backend, a truncated
    # question set - would be read as a model's headline score if they sat in
    # the main table, so they are kept for the backend note and nothing else.
    def is_variant(lbl: str) -> bool:
        # A run over a truncated question set is not a model's score. A run on a
        # second backend IS a full score and stays in the table - its row names
        # the backend, which is the comparison the reader wants to make.
        return "limit" in lbl

    partial = [(lbl, d) for lbl, d in sql_runs if is_variant(lbl)]
    sql_runs = [(lbl, d) for lbl, d in sql_runs if not is_variant(lbl)]
    rep_runs = [(n.replace("report-", ""), load(n)) for n in names if n.startswith("report-")]
    rep_runs = [(lbl, d) for lbl, d in rep_runs if d and not is_variant(lbl)]

    print("% --- execution accuracy per category ---")
    print(accuracy_rows(sql_runs))
    print("\n% --- throughput / tokens / cost ---")
    print(throughput_rows(sql_runs))
    print("\n% --- backend / decode detail for the local rows ---")
    print(backend_note(sql_runs + partial))

    print("\n% --- excel report quality ---")
    print(report_rows(rep_runs))


if __name__ == "__main__":
    main()
