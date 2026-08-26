#!/usr/bin/env python3
"""Run the benchmark question set through one arm and score it.

    # naive baseline, against a throwaway local PostgreSQL (no Docker needed)
    GEMINI_API_KEY=... python benchmark/run.py --arm naive

    # the project's pipeline, against the compose stack
    python benchmark/run.py --arm pipeline --base-url http://localhost:8100

    # an existing database instead of a throwaway one
    python benchmark/run.py --arm naive --database-url postgresql://...

Writes benchmark/results/<arm>.json and prints the summary table.

Predicted SQL is executed on a read-only connection with a statement timeout:
the queries come from a language model, and the harness must not be the thing
that lets one of them lock or mutate the evaluation database.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

import yaml

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import arms as arms_mod  # noqa: E402
from score import result_sets_match, summarise  # noqa: E402

STATEMENT_TIMEOUT_MS = 15_000


def load_questions(path: pathlib.Path) -> list[dict]:
    return yaml.safe_load(path.read_text())["questions"]


def ensure_database(database_url: str | None, repo: pathlib.Path) -> str:
    """Return a connection URL, creating a throwaway server if none was given.

    pgserver ships PostgreSQL binaries as a wheel, so the benchmark can run on a
    machine with no Docker and no system PostgreSQL — which is also what makes
    these numbers reproducible by someone marking the thesis.
    """
    if database_url:
        return database_url

    import pgserver
    import psycopg

    data_dir = repo / "benchmark" / ".pgdata"
    data_dir.mkdir(parents=True, exist_ok=True)
    srv = pgserver.get_server(str(data_dir))
    try:
        srv.psql("CREATE DATABASE car_rental;")
    except Exception:
        pass  # already exists
    uri = srv.get_uri(database="car_rental")

    with psycopg.connect(uri, autocommit=True) as c:
        exists = c.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name='vehicles'"
        ).fetchone()
        if not exists:
            c.execute((repo / "test_app_db" / "init" / "01_schema.sql").read_text())
            c.execute((repo / "benchmark_data" / "car_rental_seed_postgres.sql").read_text())
            print("seeded throwaway database from the frozen dataset")
    return uri


def schema_text(repo: pathlib.Path) -> str:
    """Whole-schema dump for the naive arm: its defining characteristic."""
    return (repo / "test_app_db" / "init" / "01_schema.sql").read_text()


def execute(conn, sql: str):
    # statement_timeout is set once at session level in main(), not with SET
    # LOCAL here: the connection is in autocommit, so each execute is its own
    # transaction and a LOCAL setting would expire before the query it guards.
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=sorted(arms_mod.REGISTRY))
    ap.add_argument("--questions", type=pathlib.Path, default=HERE / "questions.yaml")
    ap.add_argument("--database-url", default=os.environ.get("BENCHMARK_DATABASE_URL"))
    ap.add_argument("--base-url", default="http://localhost:8100", help="pipeline arm only")
    ap.add_argument("--limit", type=int, help="run only the first N questions")
    ap.add_argument("--out", type=pathlib.Path)
    args = ap.parse_args()

    repo = HERE.parent
    questions = load_questions(args.questions)
    if args.limit:
        questions = questions[: args.limit]

    import psycopg

    uri = ensure_database(args.database_url, repo)

    if args.arm == "naive":
        arm = arms_mod.make_naive_arm(schema_text(repo))
    elif args.arm == "pipeline":
        arm = arms_mod.make_pipeline_arm(args.base_url)
    else:
        arm = arms_mod.make_mcp_postgres_arm()

    results: list[dict] = []
    # Read-only: model-generated SQL must not be able to change the fixture.
    with psycopg.connect(uri, autocommit=True) as conn:
        conn.execute("SET default_transaction_read_only = on")
        conn.execute(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}")
        for i, q in enumerate(questions, 1):
            out = arm(q)
            rec = {
                "id": q["id"], "question": q["question"], "category": q["category"],
                "lang": q["lang"], "sql": out["sql"], "gold_sql": q["gold_sql"],
                "latency_ms": out["latency_ms"], "arm_error": out["error"],
                "clarified": out["clarified"], "extra": out.get("extra") or {},
            }

            if q["gold_sql"] is None:
                # Ambiguous: correctness is "did it ask rather than guess".
                rec["scored"] = False
                results.append(rec)
                mark = "ASK" if out["clarified"] else "guessed"
            else:
                rec["scored"] = True
                rec["correct"] = False
                rec["exec_error"] = None
                if out["sql"]:
                    try:
                        gold = execute(conn, q["gold_sql"])
                        pred = execute(conn, out["sql"])
                        rec["correct"] = result_sets_match(gold, pred, q.get("ordered", False))
                        rec["gold_rows"], rec["pred_rows"] = len(gold), len(pred)
                    except Exception as e:
                        rec["exec_error"] = str(e).splitlines()[0][:200]
                results.append(rec)
                mark = "ok " if rec["correct"] else ("ERR" if rec["exec_error"] else "MISS")

            print(f"  [{i:>2}/{len(questions)}] {q['id']} {mark:<8} {q['question'][:52]}")

    summary = summarise(results)
    out_path = args.out or (HERE / "results" / f"{args.arm}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(
        {"arm": args.arm, "model": os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
         "summary": summary, "results": results}, indent=2, default=str))

    print(f"\n=== {args.arm} ===")
    print(f"execution accuracy : {summary['execution_accuracy']:.1%} "
          f"({summary['n_correct']}/{summary['n_scored']})")
    for cat, s in summary["by_category"].items():
        print(f"  {cat:<10} {s['correct']:>2}/{s['n']:<3} {s['accuracy']:.0%}")
    print(f"invalid SQL        : {summary['invalid_sql']}")
    print(f"no SQL produced    : {summary['no_sql_produced']}")
    print(f"ambiguity handled  : {summary['ambiguous_clarified']}/{summary['ambiguous_total']}")
    print(f"latency median/mean: {summary['latency_ms_median']} / {summary['latency_ms_mean']} ms")
    print(f"\nwrote {out_path.relative_to(repo)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
