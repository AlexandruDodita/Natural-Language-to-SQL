"""The systems under comparison.

Each arm is a callable: question -> {sql, clarified, latency_ms, error, extra}.
Keeping them behind one interface is what lets the same question set, the same
database and the same scorer be pointed at every approach, so the numbers in
the results table differ because the approaches differ and for no other reason.

Arms:
  naive         Whole schema dumped into one prompt, one call, no retrieval and
                no repair. This is the control: it is what you get from wiring a
                model straight to a database, and it is the thing the thesis has
                to beat to justify the rest of the system.
  pipeline      The project's own rag-service pipeline over HTTP.
  mcp-postgres  The Postgres MCP server driven agentically, via its harness.

Model access is confined to `_gemini_sql()` so a local model can be substituted
in one place for the local-vs-hosted comparison.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import time
from typing import Callable

REPO = pathlib.Path(__file__).resolve().parent.parent

NAIVE_PROMPT = """You are a SQL expert for a car rental company database.

{schema}

Write a single PostgreSQL SELECT query answering the user's question.
Respond with ONLY the SQL. No markdown fences, no explanation.
If the question cannot be answered from this schema, respond with exactly: NO_SQL
"""


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t).strip()
    return t


def _gemini_sql(prompt: str, question: str) -> str:
    """Single-shot completion. The only place a hosted model is called."""
    import google.generativeai as genai

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"))
    resp = model.generate_content(f"{prompt}\n\nQuestion: {question}")
    return _strip_fences(resp.text or "")


def make_naive_arm(schema_text: str) -> Callable[[dict], dict]:
    prompt = NAIVE_PROMPT.format(schema=schema_text)

    def run(q: dict) -> dict:
        t0 = time.perf_counter()
        try:
            sql = _gemini_sql(prompt, q["question"])
            err = None
        except Exception as e:  # network, quota, safety block
            sql, err = "", f"{type(e).__name__}: {e}"
        dt = (time.perf_counter() - t0) * 1000
        no_sql = sql.strip().upper() == "NO_SQL" or not sql
        return {
            "sql": None if no_sql else sql,
            # The naive arm has no notion of asking a question back; refusing to
            # emit SQL is the closest thing it has to recognising ambiguity, and
            # scoring it as such is generous to the baseline rather than unfair.
            "clarified": no_sql and not err,
            "latency_ms": round(dt, 1),
            "error": err,
            "extra": {"prompt_chars": len(prompt)},
        }

    return run


def make_pipeline_arm(base_url: str) -> Callable[[dict], dict]:
    """The project's rag-service. Reads the SSE stream for its [META] frame."""
    import httpx

    def run(q: dict) -> dict:
        t0 = time.perf_counter()
        sql = err = None
        clarified = False
        meta: dict = {}
        try:
            with httpx.Client(timeout=120.0) as client:
                with client.stream(
                    "POST", f"{base_url}/chat",
                    json={"messages": [{"role": "user", "content": q["question"]}]},
                ) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line.startswith("data: "):
                            continue
                        payload = line[6:]
                        if payload.startswith("[META]"):
                            meta = json.loads(payload[6:])
                        elif payload.startswith("[ERROR]"):
                            err = payload[7:].strip()
                        elif payload == "[DONE]":
                            break
            sql = meta.get("sql")
            clarified = bool(meta.get("clarification") or meta.get("outcome") == "clarification")
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        return {
            "sql": sql,
            "clarified": clarified,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
            "error": err,
            "extra": {k: meta.get(k) for k in ("retrieval", "attempts", "blocked", "outcome") if k in meta},
        }

    return run


def make_mcp_postgres_arm() -> Callable[[dict], dict]:
    """Drives mcps/postgres agentically through its own client harness."""
    import sys

    sys.path.insert(0, str(REPO / "mcps" / "postgres"))
    import client_harness  # type: ignore

    def run(q: dict) -> dict:
        t0 = time.perf_counter()
        try:
            r = client_harness.ask(q["question"])
            return {
                "sql": r.get("final_sql"),
                "clarified": not r.get("final_sql") and not r.get("error"),
                "latency_ms": r.get("latency_ms") or round((time.perf_counter() - t0) * 1000, 1),
                "error": r.get("error"),
                "extra": {"tool_calls": len(r.get("tool_calls") or [])},
            }
        except Exception as e:
            return {
                "sql": None, "clarified": False,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                "error": f"{type(e).__name__}: {e}", "extra": {},
            }

    return run


REGISTRY = {
    "naive": make_naive_arm,
    "pipeline": make_pipeline_arm,
    "mcp-postgres": make_mcp_postgres_arm,
}
