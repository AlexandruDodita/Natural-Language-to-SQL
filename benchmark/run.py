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
import time

import yaml

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import arms as arms_mod  # noqa: E402
import clients  # noqa: E402
import datasets as datasets_mod  # noqa: E402
from score import result_sets_match, summarise  # noqa: E402

STATEMENT_TIMEOUT_MS = 15_000
CHECKPOINT_EVERY = 50


def load_questions(path: pathlib.Path) -> list[dict]:
    """The question set, from YAML or JSON.

    The hand-written sets are YAML because a human maintains them. A generated
    set is JSON: `questions_bird_dev.json` is 1,534 entries built by a script,
    and pushing 2 MB of that through the YAML parser costs seconds per run for
    no benefit. YAML is a superset of JSON, so this is a speed choice rather
    than a format one.
    """
    text = path.read_text()
    doc = json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)
    return doc["questions"]


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


def schema_text(repo: pathlib.Path, ds: datasets_mod.Dataset):
    """Whole-schema dump for the naive arm: its defining characteristic.

    A string for a one-database dataset, a `question -> schema` callable for a
    multi-database one. The arms accept either.
    """
    return ds.schema_for(repo)


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


class Fixture:
    """The evaluation database, and the single place model SQL is executed.

    Introduced when BIRD arrived, because until then "the database" was one
    PostgreSQL connection held open for the whole run. BIRD is 11 SQLite files
    and the right one is a property of the question, so the choice of connection
    had to move somewhere. Putting execution behind this interface keeps that
    choice out of the scoring loop, which is identical for every backend and
    should stay that way -- the metric must not vary with the engine.

    Both implementations are read-only and time-bounded. That is not a detail:
    the SQL comes from a language model, and the harness must not be the thing
    that lets one of them lock or mutate the fixture.
    """

    def execute(self, q: dict, sql: str):
        raise NotImplementedError

    def close(self) -> None:
        pass


class PostgresFixture(Fixture):
    def __init__(self, uri: str, ds: datasets_mod.Dataset):
        import psycopg
        self.uri = uri
        self.conn = psycopg.connect(uri, autocommit=True)
        self.conn.execute("SET default_transaction_read_only = on")
        self.conn.execute(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}")
        if ds.search_path:
            self.conn.execute(f"SET search_path = {ds.search_path}")

    def execute(self, q: dict, sql: str):
        # statement_timeout is set once at session level above, not with SET
        # LOCAL here: the connection is in autocommit, so each execute is its
        # own transaction and a LOCAL setting would expire before the query it
        # guards.
        with self.conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()

    def close(self) -> None:
        self.conn.close()


class SqliteFixture(Fixture):
    """One read-only connection per database, opened on first use and kept.

    SQLite has no `statement_timeout`, so the bound is a progress handler that
    aborts the running statement once a wall-clock deadline passes. Without it
    a single model-generated cross join against the 600 MB football database
    stalls the run indefinitely, which on a 1,534-question set means losing a
    whole overnight to one bad query.
    """

    def __init__(self, ds, repo: pathlib.Path):
        self.ds, self.repo = ds, repo
        self.conns: dict[str, "sqlite3.Connection"] = {}

    def _conn(self, db_id: str):
        import sqlite3
        if db_id not in self.conns:
            path = self.ds.sqlite_path(self.repo, db_id)
            if not path.exists():
                raise SystemExit(
                    f"missing database {path}. Run benchmark_data/bird/prepare.py "
                    f"after unpacking the BIRD dev bundle.")
            self.conns[db_id] = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        return self.conns[db_id]

    def execute(self, q: dict, sql: str):
        conn = self._conn(q["db_id"])
        end = time.perf_counter() + STATEMENT_TIMEOUT_MS / 1000
        conn.set_progress_handler(
            lambda: 1 if time.perf_counter() > end else 0, 10_000)
        try:
            return conn.execute(sql).fetchall()
        finally:
            conn.set_progress_handler(None, 0)

    def close(self) -> None:
        for c in self.conns.values():
            c.close()


def open_fixture(args, repo: pathlib.Path, ds: datasets_mod.Dataset) -> Fixture:
    if ds.backend == "sqlite":
        if args.database_url:
            raise SystemExit(f"--database-url does not apply to {ds.name} (SQLite)")
        return SqliteFixture(ds, repo)
    return PostgresFixture(ensure_database(args.database_url, repo, ds), ds)


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
    ap.add_argument("--agent-model", default="claude-opus-5",
                    help="model for the claude-agent arm (e.g. claude-opus-5)")
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

    fixture = open_fixture(args, repo, ds)
    # The agent arms drive an MCP server that speaks to PostgreSQL over a URI.
    # There is no such server for the SQLite datasets, and silently running them
    # against the wrong database would be worse than refusing.
    if args.arm in ("claude-agent", "codex-agent", "mcp-postgres", "pipeline") \
            and ds.backend != "postgres":
        raise SystemExit(f"the {args.arm} arm needs a PostgreSQL fixture; "
                         f"{ds.name} is {ds.backend}")
    uri = getattr(fixture, "uri", None)

    if args.arm == "naive":
        arm = arms_mod.make_naive_arm(schema_text(repo, ds), domain=ds.domain,
                                      dialect=ds.dialect)
        model_label = clients.gemini_model_name()
    elif args.arm == "local":
        arm = arms_mod.make_local_arm(schema_text(repo, ds), args.local_base_url,
                                      args.local_model, domain=ds.domain,
                                      dialect=ds.dialect)
        model_label = args.local_model
    elif args.arm == "pipeline":
        arm = arms_mod.make_pipeline_arm(args.base_url)
        model_label = clients.gemini_model_name()
    elif args.arm == "claude-agent":
        # The agent explores the live database instead of being handed a schema,
        # so it needs the MCP server pointed at the same URI the scorer uses.
        # Written per run rather than committed: it embeds an absolute socket
        # path that is only valid on this machine.
        cfg = HERE / ".mcp-agent-config.json"
        cfg.write_text(json.dumps({"mcpServers": {"postgres": {
            "command": sys.executable,
            "args": [str(repo / "mcps" / "postgres" / "server.py")],
            "env": {"DATABASE_URL": uri, "MAX_ROWS": "100",
                    "STATEMENT_TIMEOUT_MS": str(STATEMENT_TIMEOUT_MS)},
        }}}, indent=2))
        arm = arms_mod.make_claude_agent_arm(args.agent_model, domain=ds.domain)
        model_label = args.agent_model
    elif args.arm == "codex-agent":
        cfg = HERE / ".mcp-agent-config.json"
        cfg.write_text(json.dumps({"mcpServers": {"postgres": {
            "command": sys.executable,
            "args": [str(repo / "mcps" / "postgres" / "server.py")],
            "env": {"DATABASE_URL": uri, "MAX_ROWS": "100",
                    "STATEMENT_TIMEOUT_MS": str(STATEMENT_TIMEOUT_MS)},
        }}}, indent=2))
        arm = arms_mod.make_codex_agent_arm(args.agent_model, domain=ds.domain)
        model_label = args.agent_model
    else:
        arm = arms_mod.make_mcp_postgres_arm()
        model_label = clients.gemini_model_name()

    # car_rental keeps writing results/<arm>.json so existing files and the
    # table generator are untouched; other datasets get their own subdirectory.
    default_out = (HERE / "results" / f"{args.arm}.json" if args.dataset == datasets_mod.DEFAULT
                   else HERE / "results" / args.dataset / f"{args.arm}.json")
    out_path = args.out or default_out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # A 1,534-question run is hours long and used to write nothing until the
    # last question returned, so a crash at question 1,500 threw away the
    # entire API spend. The checkpoint is answers-only: it is a crash bag to
    # re-score from, never a results file, which is why it is written to a
    # different name and deleted the moment the real one lands.
    ckpt_path = out_path.with_suffix(".partial.json")

    results: list[dict] = []
    try:
        for i, q in enumerate(questions, 1):
            out = arm(q)
            rec = {
                "id": q["id"], "question": q["question"], "category": q["category"],
                "lang": q["lang"], "sql": out["sql"], "gold_sql": q["gold_sql"],
                "latency_ms": out["latency_ms"], "arm_error": out["error"],
                "clarified": out["clarified"], "usage": out.get("usage"),
                "extra": out.get("extra") or {},
            }
            if q.get("db_id"):
                rec["db_id"] = q["db_id"]

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
                    # Gold and prediction are executed in separate blocks so
                    # their failures cannot be confused. A gold that will not
                    # run is a broken question -- it costs every arm the same
                    # point and says nothing about any model -- whereas a
                    # prediction that will not run is the result being
                    # measured. Collapsing both into `exec_error` would report
                    # the first as the second, and `invalid_sql` in the summary
                    # would count questions no model got wrong.
                    gold = None
                    try:
                        gold = fixture.execute(q, q["gold_sql"])
                    except Exception as e:
                        rec["gold_error"] = str(e).splitlines()[0][:200]
                    if gold is not None and not gold:
                        # A gold query returning nothing makes the question
                        # unscoreable rather than hard: the comparison sees
                        # two empty result sets and matches them, so any
                        # query that returns no rows -- including a wrong
                        # one -- is marked correct. Fail loudly instead of
                        # quietly inflating the score.
                        raise SystemExit(
                            f"{q['id']}: gold SQL returns zero rows against "
                            f"{args.dataset}. An empty gold is trivially "
                            f"matchable; fix the question or the fixture.")
                    if gold:
                        try:
                            pred = fixture.execute(q, out["sql"])
                            rec["correct"] = result_sets_match(
                                gold, pred, q.get("ordered", False))
                            rec["gold_rows"], rec["pred_rows"] = len(gold), len(pred)
                        except Exception as e:
                            rec["exec_error"] = str(e).splitlines()[0][:200]
                results.append(rec)
                mark = ("ok " if rec["correct"] else
                        "GOLD?" if rec.get("gold_error") else
                        "ERR" if rec["exec_error"] else "MISS")

            print(f"  [{i:>4}/{len(questions)}] {q['id']} {mark:<8} "
                  f"{q['question'][:52]}", flush=True)
            if i % CHECKPOINT_EVERY == 0:
                ckpt_path.write_text(json.dumps(
                    {"arm": args.arm, "dataset": args.dataset, "model": model_label,
                     "answered": i, "of": len(questions), "results": results},
                    indent=1, default=str))
    finally:
        fixture.close()

    summary = summarise(results)
    summary["usage"] = clients.aggregate_usage([r.get("usage") for r in results])
    summary["cost"] = cost_block(model_label, summary["usage"], len(results),
                                 local=args.arm == "local")
    # An arm that knows what it actually spent beats an extrapolation from list
    # prices: the agent arm re-reads a large cached prefix every turn, which the
    # per-token estimate cannot see. Recorded alongside, never instead of, so the
    # two are comparable across arms.
    billed = [r["extra"]["cost_usd"] for r in results
              if (r.get("extra") or {}).get("cost_usd") is not None]
    if billed:
        summary["cost"]["usd_per_100_questions_measured"] = round(
            sum(billed) / len(billed) * 100, 4)
        summary["cost"]["measured_questions"] = len(billed)

    payload = {"arm": args.arm, "dataset": args.dataset, "model": model_label,
               "questions_fingerprint": fingerprint,
               "summary": summary, "results": results}
    if args.arm == "local":
        payload["backend"] = clients.LOCAL_BACKEND or "unspecified ($LOCAL_BACKEND not set)"
        payload["endpoint"] = args.local_base_url
    out_path.write_text(json.dumps(payload, indent=2, default=str))
    ckpt_path.unlink(missing_ok=True)

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
