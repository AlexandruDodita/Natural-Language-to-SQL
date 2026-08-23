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
from score import result_sets_match, summarise  # noqa: E402

REPO = HERE.parent


def db_uri() -> str:
    import pgserver
    srv = pgserver.get_server(str(REPO / "benchmark" / ".pgdata"), cleanup_mode=None)
    return srv.get_uri(database="car_rental")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    import psycopg
    questions = {q["id"]: q for q in
                 __import__("yaml").safe_load((HERE / "questions.yaml").read_text())["questions"]}

    with psycopg.connect(db_uri(), autocommit=True) as conn:
        conn.execute("SET default_transaction_read_only = on")
        conn.execute("SET statement_timeout = 15000")

        def run(sql):
            with conn.cursor() as cur:
                cur.execute(sql)
                return cur.fetchall()

        for path in sorted((HERE / "results").rglob("*.json")):
            doc = json.loads(path.read_text())
            # results/ also holds the Excel scorer's output, which has a
            # different shape and nothing to re-execute.
            if "execution_accuracy" not in (doc.get("summary") or {}):
                print(f"  {path.name:<44} skipped (not an arm result)")
                continue
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
            # summarise() rebuilds usage from the per-question records; the cost
            # block depends on published prices, so recompute it the same way
            # run.py does rather than carrying a stale figure forward.
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
