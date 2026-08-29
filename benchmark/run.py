#!/usr/bin/env python3
"""Run the benchmark question set through one arm and score it.

    # naive baseline, against a throwaway local PostgreSQL (no Docker needed)
    GEMINI_API_KEY=... python benchmark/run.py --arm naive

    # the same baseline on another hosted model, into its own results file
    GEMINI_MODEL=gemini-3.7-flash python benchmark/run.py --arm naive \
        --out benchmark/results/naive-gemini-3.7-flash.json

    # the same baseline on a model served locally over an OpenAI-compatible API
    python benchmark/run.py --arm local --local-model qwen3.5-9b \
        --local-base-url http://127.0.0.1:1234/v1

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
import clients  # noqa: E402
import datasets as datasets_mod  # noqa: E402
from score import result_sets_match, summarise  # noqa: E402

STATEMENT_TIMEOUT_MS = 15_000


def load_questions(path: pathlib.Path) -> list[dict]:
    return yaml.safe_load(path.read_text())["questions"]


def ensure_database(database_url: str | None, repo: pathlib.Path,
                    ds: datasets_mod.Dataset) -> str:
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
        srv.psql(f"CREATE DATABASE {ds.db_name};")
    except Exception:
        pass  # already exists
    uri = srv.get_uri(database=ds.db_name)

    with psycopg.connect(uri, autocommit=True) as c:
        if not c.execute(ds.probe_sql).fetchone():
            ds.seed(c, repo)
    return uri


def schema_text(repo: pathlib.Path, ds: datasets_mod.Dataset) -> str:
    """Whole-schema dump for the naive arm: its defining characteristic."""
    return ds.schema_text(repo)


def cost_block(model: str, usage: dict, n_questions: int, local: bool = False) -> dict:
    """Extrapolate the measured token usage to a per-100-question API bill.

    Only models with a price verified against the published rate card get a
    number; anything else gets a note, because a fabricated cost is worse than
    an absent one. A locally served model has no per-token bill at all, which
    is reported as zero with the reason attached rather than left blank.
    """
    if not usage or not n_questions:
        return {}
    if local:
        return {"model": model, "usd_per_100_questions": 0.0,
                "note": "served locally: no per-token API charge; the cost is "
                        "the hardware and the electricity to run it"}
    price = clients.PRICING_USD_PER_MTOK.get(model)
    if not price:
        return {"model": model, "usd_per_100_questions": None,
                "note": f"no verified published price for {model}"}
    per_q_in = usage["prompt_tokens_total"] / n_questions
    per_q_out = usage["output_tokens_total"] / n_questions
    usd = clients.estimate_cost_usd(model, per_q_in * 100, per_q_out * 100)
    return {
        "model": model,
        "usd_per_mtok_input": price["input"],
        "usd_per_mtok_output": price["output"],
        "prices_checked": clients.PRICING_CHECKED,
        "usd_per_100_questions": round(usd, 6) if usd is not None else None,
    }


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
    ap.add_argument("--dataset", default=datasets_mod.DEFAULT,
                    choices=sorted(datasets_mod.REGISTRY),
                    help="which evaluation database to run against")
    ap.add_argument("--questions", type=pathlib.Path,
                    help="override the dataset's question set")
    ap.add_argument("--database-url", default=os.environ.get("BENCHMARK_DATABASE_URL"))
    ap.add_argument("--base-url", default="http://localhost:8100", help="pipeline arm only")
    ap.add_argument("--local-base-url", default=clients.DEFAULT_LOCAL_BASE_URL,
                    help="local arm only: OpenAI-compatible endpoint")
    ap.add_argument("--local-model", default=clients.DEFAULT_LOCAL_MODEL,
                    help="local arm only: model id the endpoint serves")
    ap.add_argument("--limit", type=int, help="run only the first N questions")
    ap.add_argument("--out", type=pathlib.Path)
    args = ap.parse_args()

    repo = HERE.parent
    ds = datasets_mod.REGISTRY[args.dataset]
    questions = load_questions(args.questions or ds.questions_path(HERE))
    # Fingerprint the whole set, not the truncated one: a --limit run answers a
    # prefix of the same questions and is not a different experiment.
    fingerprint = datasets_mod.questions_fingerprint(questions)
    if args.limit:
        questions = questions[: args.limit]

    import psycopg

    uri = ensure_database(args.database_url, repo, ds)

    if args.arm == "naive":
        arm = arms_mod.make_naive_arm(schema_text(repo, ds), domain=ds.domain)
        model_label = clients.gemini_model_name()
    elif args.arm == "local":
        arm = arms_mod.make_local_arm(schema_text(repo, ds), args.local_base_url,
                                      args.local_model, domain=ds.domain)
        model_label = args.local_model
    elif args.arm == "pipeline":
        arm = arms_mod.make_pipeline_arm(args.base_url)
        model_label = clients.gemini_model_name()
    else:
        arm = arms_mod.make_mcp_postgres_arm()
        model_label = clients.gemini_model_name()

    results: list[dict] = []
    # Read-only: model-generated SQL must not be able to change the fixture.
    with psycopg.connect(uri, autocommit=True) as conn:
        conn.execute("SET default_transaction_read_only = on")
        conn.execute(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}")
        if ds.search_path:
            conn.execute(f"SET search_path = {ds.search_path}")
        for i, q in enumerate(questions, 1):
            out = arm(q)
            rec = {
                "id": q["id"], "question": q["question"], "category": q["category"],
                "lang": q["lang"], "sql": out["sql"], "gold_sql": q["gold_sql"],
                "latency_ms": out["latency_ms"], "arm_error": out["error"],
                "clarified": out["clarified"], "usage": out.get("usage"),
                "extra": out.get("extra") or {},
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
    summary["usage"] = clients.aggregate_usage([r.get("usage") for r in results])
    summary["cost"] = cost_block(model_label, summary["usage"], len(results),
                                 local=args.arm == "local")

    # car_rental keeps writing results/<arm>.json so existing files and the
    # table generator are untouched; other datasets get their own subdirectory.
    default_out = (HERE / "results" / f"{args.arm}.json" if args.dataset == datasets_mod.DEFAULT
                   else HERE / "results" / args.dataset / f"{args.arm}.json")
    out_path = args.out or default_out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"arm": args.arm, "dataset": args.dataset, "model": model_label,
               "questions_fingerprint": fingerprint,
               "summary": summary, "results": results}
    if args.arm == "local":
        payload["backend"] = clients.LOCAL_BACKEND or "unspecified ($LOCAL_BACKEND not set)"
        payload["endpoint"] = args.local_base_url
    out_path.write_text(json.dumps(payload, indent=2, default=str))

    print(f"\n=== {args.arm} ===")
    print(f"execution accuracy : {summary['execution_accuracy']:.1%} "
          f"({summary['n_correct']}/{summary['n_scored']})")
    for cat, s in summary["by_category"].items():
        print(f"  {cat:<10} {s['correct']:>2}/{s['n']:<3} {s['accuracy']:.0%}")
    print(f"invalid SQL        : {summary['invalid_sql']}")
    print(f"no SQL produced    : {summary['no_sql_produced']}")
    print(f"ambiguity handled  : {summary['ambiguous_clarified']}/{summary['ambiguous_total']}")
    print(f"latency median/mean: {summary['latency_ms_median']} / {summary['latency_ms_mean']} ms")
    u = summary["usage"]
    if u:
        print(f"tokens/s mean/median: {u['tokens_per_sec_mean']} / {u['tokens_per_sec_median']}")
        if u.get("decode_tokens_per_sec_mean"):
            print(f"  decode-only tok/s  : {u['decode_tokens_per_sec_mean']}")
        if u.get("ttft_ms_median"):
            print(f"  TTFT median        : {u['ttft_ms_median']} ms")
        print(f"prompt/output tokens: {u['prompt_tokens_total']} / {u['output_tokens_total']} "
              f"(of which {u['thinking_tokens_total']} reasoning)")
    c = summary["cost"] or {}
    if c.get("usd_per_100_questions") is not None:
        suffix = (f"(prices checked {c['prices_checked']})" if c.get("prices_checked")
                  else f"({c.get('note', '')})")
        print(f"cost per 100 questions: ${c['usd_per_100_questions']:.4f} {suffix}")
    elif c.get("note"):
        print(f"cost per 100 questions: {c['note']}")
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
