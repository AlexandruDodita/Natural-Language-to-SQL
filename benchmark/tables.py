#!/usr/bin/env python3
"""Renders the results JSONs as the LaTeX table bodies used in the thesis.

    python benchmark/tables.py                        # car_rental
    python benchmark/tables.py --dataset adventureworks

Every number in the results chapter is printed by this script from the JSON the
harness wrote, so a table in the document can be regenerated from the measured
data instead of being retyped - and a typo in the thesis is a diff away from
being caught.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = HERE / "results"
# The five original categories are one column each. The eleven added with the
# second wave of questions are not: sixteen columns is not a table anyone reads,
# so they are grouped by what the question tests. The grouping lives here rather
# than in the question files because it is a presentation choice -- the results
# files keep the ungrouped per-question category, so a different cut of the same
# runs costs an edit here and no re-running.
CATEGORY_GROUPS: list[tuple[str, list[str]]] = [
    ("simple", ["simple"]),
    ("aggregate", ["aggregate"]),
    ("join", ["join"]),
    ("subquery", ["subquery"]),
    ("window", ["window"]),
    # Getting the structure of the query right: how many aggregation levels,
    # which join shape, whether NULLs are handled.
    ("structure", ["multi_level_agg", "self_join", "anti_join", "recursive",
                   "set_ops", "gaps_islands"]),
    # Getting the measure right once the rows are correct.
    ("measure", ["ratio", "percentile", "pivot"]),
    # Getting the period right: which prior period, and whether empty ones count.
    ("time", ["temporal", "calendar", "cohort"]),
]
CATEGORIES = [name for name, _ in CATEGORY_GROUPS]
_GROUPED = {c for _, members in CATEGORY_GROUPS for c in members}


def group_accuracy(by_category: dict, members: list[str]) -> float | None:
    """Accuracy over a group of categories, weighted by question count.

    Averaging the per-category percentages would weight a two-question category
    the same as a six-question one. Returns None when the run answered nothing
    in the group, which prints as a dash rather than as a zero.
    """
    n = sum(by_category.get(c, {}).get("n", 0) for c in members)
    if not n:
        return None
    return sum(by_category.get(c, {}).get("correct", 0) for c in members) / n


def load(name: str) -> dict | None:
    p = RESULTS / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def pct(x: float | None) -> str:
    return f"{x * 100:.1f}\\%" if x is not None else "--"


def num(x, d: int = 1) -> str:
    return f"{x:.{d}f}" if isinstance(x, (int, float)) else "--"


CURRENT_FINGERPRINT: str | None = None


def is_stale(run: dict | None) -> bool:
    """True when a results file answers a question set that no longer exists.

    Rewording a question invalidates every stored answer to it, and the failure
    is silent -- the file still parses, the percentages still add up, they just
    describe a different experiment. Files written before fingerprinting existed
    carry no fingerprint and are treated as stale, which is the safe reading.
    """
    if CURRENT_FINGERPRINT is None:
        return False
    return (run or {}).get("questions_fingerprint") != CURRENT_FINGERPRINT


def tex_model(name: str, run: dict | None = None) -> str:
    """The model's name, plus the backend for a local run.

    A local throughput figure is meaningless without the engine that produced
    it, so the backend travels with the label rather than living in a footnote.
    A row scored against a superseded question set is marked, because printing
    it next to current rows without a word is how a stale number reaches print.
    """
    stale = "\\textsuperscript{*}" if is_stale(run) else ""
    backend = (run or {}).get("backend") or ""
    for tag in ("CUDA", "Vulkan", "CPU"):
        if tag.lower() in backend.lower():
            # The file name may already carry the backend to keep two runs of
            # one model apart; the label should not say it twice.
            bare = name[: -len(tag) - 1] if name.lower().endswith("-" + tag.lower()) else name
            return "\\code{" + bare.replace("_", "\\_") + "}" + f" ({tag}){stale}"
    return "\\code{" + name.replace("_", "\\_") + "}" + stale


def accuracy_rows(runs: list[tuple[str, dict]]) -> str:
    out = []
    for label, d in runs:
        s = d["summary"]
        by_cat = s["by_category"]
        ungrouped = sorted(set(by_cat) - _GROUPED)
        if ungrouped:
            # A category with no column is silently missing from the table but
            # still counted in the total, which is how a column and its total
            # stop agreeing without anyone noticing.
            print(f"% WARNING: {label}: category not in any column: "
                  f"{', '.join(ungrouped)}", file=sys.stderr)
        cells = [pct(group_accuracy(by_cat, members)) for _, members in CATEGORY_GROUPS]
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
            tex_model(label, d),
            f"{s['chart_type_correct']}/{s['n']}",
            pct(s["chart_type_accuracy"]),
            pct(s.get("chart_type_accuracy_chartable")),
            pct(s.get("chart_type_accuracy_scalar")),
            pct(s["structural_validity"]),
        ]) + " \\\\")
    return "\n".join(out)


def arm_rows(runs: list[tuple[str, dict]]) -> str:
    """The arm comparison: one row per system, not per model.

    These are the rows the thesis's central claim rests on, and until now they
    had no renderer -- `pipeline.json` and `mcp-postgres.json` were scanned for
    staleness and then dropped on the floor. The agent arms made the omission
    expensive, because an agent's whole point is that it is a different system
    rather than a different model.

    Cost is the measured column where an arm reports one. An agent re-sends a
    large cached prefix every turn and cache reads are billed at a fraction of
    the input rate, so extrapolating from list prices overstates it; where the
    CLI told us what it actually charged, that is the number printed, and the
    column header should say so.
    """
    out = []
    for label, d in runs:
        s = d["summary"]
        cost = (s.get("cost") or {})
        usd = cost.get("usd_per_100_questions_measured")
        usd_s = f"{usd:.2f}" if isinstance(usd, (int, float)) else "--"
        u = s.get("usage") or {}
        out.append(" & ".join([
            tex_model(label, d),
            f"{s['n_correct']}/{s['n_scored']}",
            f"\\textbf{{{pct(s['execution_accuracy'])}}}",
            f"{s['ambiguous_clarified']}/{s['ambiguous_total']}",
            num(s.get("latency_ms_median", 0) / 1000 if s.get("latency_ms_median") else None, 2),
            str(int(u["prompt_tokens_mean"])) if u.get("prompt_tokens_mean") else "--",
            usd_s,
        ]) + " \\\\")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="car_rental",
                    help="which dataset's results to render; car_rental reads "
                         "results/, anything else reads results/<dataset>/")
    args = ap.parse_args()
    global RESULTS
    if args.dataset != "car_rental":
        RESULTS = HERE / "results" / args.dataset
        if not RESULTS.is_dir():
            raise SystemExit(f"no results directory for dataset {args.dataset!r}: {RESULTS}")

    # Fingerprint of the question set these results are being rendered against.
    import datasets as datasets_mod
    import yaml
    global CURRENT_FINGERPRINT
    ds = datasets_mod.REGISTRY[args.dataset]
    CURRENT_FINGERPRINT = datasets_mod.questions_fingerprint(
        yaml.safe_load(ds.questions_path(HERE).read_text())["questions"])

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

    # One row per system. `naive.json` is the arm run of the naive baseline and
    # belongs here; the `naive-<model>` files are the model sweep above.
    ARM_PREFIXES = ("claude-agent-", "codex-agent-")
    arm_runs = []
    for n in names:
        if n in ("naive", "pipeline", "mcp-postgres"):
            arm_runs.append((n, load(n)))
        elif n.startswith(ARM_PREFIXES):
            arm, _, model = n.partition("-")
            arm_runs.append((f"{arm}-agent: {n.split('-agent-', 1)[1]}", load(n)))
    arm_runs = [(lbl, d) for lbl, d in arm_runs
                if d and "execution_accuracy" in (d.get("summary") or {})]
    if arm_runs:
        print("\n% --- arm comparison (cost column is MEASURED where reported) ---")
        print(arm_rows(arm_runs))

    print("\n% --- excel report quality ---")
    print(report_rows(rep_runs))

    # Scan every arm result, not just the rendered rows: pipeline.json and
    # mcp-postgres.json belong to the arm comparison rather than these tables,
    # and a stale file nobody prints is still a stale file somebody will cite.
    stale = []
    for path in sorted(RESULTS.rglob("*.json")):
        doc = json.loads(path.read_text())
        summary = doc.get("summary") or {}
        if "execution_accuracy" not in summary and "chart_type_accuracy" not in summary:
            continue
        # results/ nests one directory per non-default dataset, so the walk sees
        # other datasets' files; they are not stale, they are someone else's.
        if doc.get("dataset", datasets_mod.DEFAULT) != args.dataset:
            continue
        if is_stale(doc):
            stale.append(path.relative_to(RESULTS))
    if stale:
        print("\n% --- STALE ---")
        print("% Rows marked * were scored against a superseded question set and are")
        print("% not comparable with the rest of the table. Re-run before citing:")
        for rel in stale:
            print(f"%   {rel}")


if __name__ == "__main__":
    main()
