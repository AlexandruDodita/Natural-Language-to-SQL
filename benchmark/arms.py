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
  local         The naive arm's prompt and contract, sent to a locally served
                model over an OpenAI-compatible API. Deliberately identical to
                `naive` in everything except which model answers, so the
                hosted-versus-local rows of the results table differ only in
                the model.

Model access is confined to `clients.py` so a local model can be substituted in
one place for the local-vs-hosted comparison, and so both back ends report the
same token and throughput record.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import time
from typing import Callable, Optional

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

import clients  # noqa: E402

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


def _single_shot_arm(prompt: str, complete) -> Callable[[dict], dict]:
    """The naive contract, parameterised only by which model answers.

    `complete` is a `prompt -> (text, Usage)` callable from clients.py. Both the
    hosted and the local arm are built from this function, which is what
    guarantees the two are comparable: same prompt, same one call, same
    interpretation of a refusal.
    """

    def run(q: dict) -> dict:
        t0 = time.perf_counter()
        usage: Optional[clients.Usage] = None
        try:
            text, usage = complete(f"{prompt}\n\nQuestion: {q['question']}")
            sql, err = _strip_fences(text), None
        except Exception as e:  # network, quota, safety block, local server down
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
            "usage": usage.as_dict() if usage else None,
            "extra": {"prompt_chars": len(prompt)},
        }

    return run


def make_naive_arm(schema_text: str) -> Callable[[dict], dict]:
    prompt = NAIVE_PROMPT.format(schema=schema_text)
    return _single_shot_arm(prompt, clients.gemini_complete)


def make_local_arm(
    schema_text: str,
    base_url: str = clients.DEFAULT_LOCAL_BASE_URL,
    model: str = clients.DEFAULT_LOCAL_MODEL,
) -> Callable[[dict], dict]:
    """The naive arm, answered by a model running on this machine.

    Any OpenAI-compatible server will do (llama.cpp's llama-server, LM Studio,
    vLLM, Ollama); the arm only needs `POST {base_url}/chat/completions`.
    """
    prompt = NAIVE_PROMPT.format(schema=schema_text)
    return _single_shot_arm(
        prompt, lambda p: clients.local_complete(p, base_url=base_url, model=model))


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
            # The pipeline makes several model calls per question and does not
            # report their token usage over the wire, so it has no usage record.
            "usage": meta.get("usage"),
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
                "usage": r.get("usage"),
                "extra": {"tool_calls": len(r.get("tool_calls") or [])},
            }
        except Exception as e:
            return {
                "sql": None, "clarified": False,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                "error": f"{type(e).__name__}: {e}", "usage": None, "extra": {},
            }

    return run


REGISTRY = {
    "naive": make_naive_arm,
    "local": make_local_arm,
    "pipeline": make_pipeline_arm,
    "mcp-postgres": make_mcp_postgres_arm,
}
