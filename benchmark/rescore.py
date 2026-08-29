#!/usr/bin/env python3
"""Re-score committed benchmark results without re-calling any model.

Every results file stores the SQL each arm produced alongside the gold SQL, so
when the scorer changes the honest move is to re-execute both and recompute -
not to re-run the models. Re-running would mix a scorer change with fresh
sampling noise (a repeat run of the same model has moved by ~8 points here),
making it impossible to say which caused a number to move.

    python benchmark/rescore.py            # rewrite every results file in place
    python benchmark/rescore.py --dry-run  # report what would change
"""
from __future__ import annotations

import argparse, json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import datasets as datasets_mod  # noqa: E402
from score import result_sets_match, summarise  # noqa: E402

REPO = HERE.parent


def db_uri(ds: datasets_mod.Dataset) -> str:
    import pgserver
    srv = pgserver.get_server(str(REPO / "benchmark" / ".pgdata"), cleanup_mode=None)
    return srv.get_uri(database=ds.db_name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    import psycopg

    # Results are grouped by dataset before anything is executed. Both question
    # sets number their questions q01..q30, so re-scoring an adventureworks file
    # against car_rental's gold SQL would not error -- it would silently produce
    # confident, wrong numbers. Files written before --dataset existed carry no
    # "dataset" key and are car_rental by definition.
    groups: dict[str, list] = {}
    for path in sorted((HERE / "results").rglob("*.json")):
        doc = json.loads(path.read_text())
        # results/ also holds the Excel scorer's output, which has a
        # different shape and nothing to re-execute.
        if "execution_accuracy" not in (doc.get("summary") or {}):
            print(f"  {path.name:<44} skipped (not an arm result)")
            continue
        groups.setdefault(doc.get("dataset", datasets_mod.DEFAULT), []).append((path, doc))

    for ds_name, items in sorted(groups.items()):
        ds = datasets_mod.REGISTRY[ds_name]
        questions = {q["id"]: q for q in
                     __import__("yaml").safe_load(ds.questions_path(HERE).read_text())["questions"]}
        print(f"[{ds_name}] {len(items)} file(s)")

        with psycopg.connect(db_uri(ds), autocommit=True) as conn:
            conn.execute("SET default_transaction_read_only = on")
            conn.execute("SET statement_timeout = 15000")
            if ds.search_path:
                conn.execute(f"SET search_path = {ds.search_path}")

            def run(sql):
                with conn.cursor() as cur:
                    cur.execute(sql)
                    return cur.fetchall()

            for path, doc in items:
                changed = []
                for rec in doc["results"]:
                    if not rec.get("scored") or not rec.get("sql"):
                        continue
                    q = questions.get(rec["id"])
                    if not q or not q.get("gold_sql"):
                        continue
                    before = rec.get("correct")
                    try:
                        ok = result_sets_match(run(q["gold_sql"]), run(rec["sql"]),
                                               q.get("ordered", False))
                        rec["correct"], rec["exec_error"] = ok, None
                    except Exception as e:
                        rec["correct"], rec["exec_error"] = False, str(e).splitlines()[0][:200]
                    if before != rec["correct"]:
                        changed.append(f"{rec['id']} {before}->{rec['correct']}")
                old_acc = doc["summary"]["execution_accuracy"]
                prev_cost = doc["summary"].get("cost")
                doc["summary"] = summarise(doc["results"])
                # summarise() rebuilds usage from the per-question records; the
                # cost block depends on published prices, so recompute it the
                # same way run.py does rather than carrying a stale figure.
                try:
                    import run as run_mod
                    doc["summary"]["cost"] = run_mod.cost_block(
                        doc.get("model", ""), doc["summary"].get("usage") or {},
                        doc["summary"].get("n_scored") or 0,
                        local=(doc.get("arm") == "local"))
                except Exception:
                    if prev_cost:
                        doc["summary"]["cost"] = prev_cost
                new_acc = doc["summary"]["execution_accuracy"]
                flag = "" if not changed else "  <- " + ", ".join(changed)
                print(f"  {path.name:<44} {old_acc:.1%} -> {new_acc:.1%}{flag}")
                if not args.dry_run:
                    path.write_text(json.dumps(doc, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
