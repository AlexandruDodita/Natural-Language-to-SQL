"""
client_harness.py — programmatic driver for the postgres MCP baseline.

This is what the thesis's evaluation harness imports. It spins up
server.py as a subprocess over stdio (via the official MCP SDK's
`mcp.client.stdio`, not by shelling out to a CLI), drives a Gemini
tool-calling loop against it for one natural-language question, and
returns a structured, JSON-able result:

    {
        "question": str,
        "final_sql": str | None,       # the SQL of the last run_query call
        "columns": list[str],
        "rows": list[list],
        "row_count": int,
        "answer_text": str,            # the model's natural-language answer
        "tool_calls": [ {tool, arguments, duration_ms, is_error,
                          result_preview}, ... ],
        "latency_ms": float,           # wall-clock, whole question
        "error": str | None,
    }

Usage (see README.md for more):

    from client_harness import ask
    result = ask("How many vehicles are currently available?")

    # or, from an async evaluator:
    from client_harness import ask_async
    result = await ask_async("...")
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

from llm_gemini import GeminiToolCaller  # noqa: E402

SERVER_SCRIPT = _THIS_DIR / "server.py"

MAX_TOOL_ROUNDS = int(os.environ.get("MCP_HARNESS_MAX_ROUNDS", "8"))
RESULT_PREVIEW_CHARS = 500

SYSTEM_INSTRUCTION = """\
You are a careful data analyst answering questions about a car rental \
company's PostgreSQL database ("car_rental"), using only the tools \
provided: list_tables, describe_table, get_schema, run_query.

Rules:
- Before writing SQL, call get_schema() (or list_tables()/describe_table() \
  if you only need part of the schema) so you know the real table and \
  column names. Never guess at schema.
- Only SELECT (or WITH ... SELECT) statements are permitted; run_query \
  will reject anything else.
- Your last tool call before answering must be run_query, with SQL that \
  fully answers the question.
- After you see the run_query result, reply with a short, direct \
  natural-language answer to the original question. Do not call any more \
  tools once you have an answer.
"""


@dataclass
class HarnessResult:
    question: str
    final_sql: str | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    row_count: int = 0
    answer_text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    latency_ms: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "final_sql": self.final_sql,
            "columns": self.columns,
            "rows": self.rows,
            "row_count": self.row_count,
            "answer_text": self.answer_text,
            "tool_calls": self.tool_calls,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


def _extract_tool_payload(call_result) -> Any:
    """FastMCP tools returning plain dict/list are (in the current MCP SDK)
    serialized as a single JSON TextContent block rather than
    structuredContent, so try structuredContent first and fall back to
    parsing the text block(s) as JSON."""
    structured = getattr(call_result, "structuredContent", None)
    if structured:
        return structured
    texts = [
        c.text for c in call_result.content if getattr(c, "type", None) == "text"
    ]
    if not texts:
        return None
    joined = "\n".join(texts)
    try:
        return json.loads(joined)
    except json.JSONDecodeError:
        return joined


def _preview(payload: Any, limit: int = RESULT_PREVIEW_CHARS) -> Any:
    s = payload if isinstance(payload, str) else json.dumps(payload, default=str)
    return s if len(s) <= limit else s[:limit] + "…"


async def ask_async(
    question: str,
    *,
    model_name: str | None = None,
    max_rounds: int = MAX_TOOL_ROUNDS,
    env: dict[str, str] | None = None,
) -> HarnessResult:
    """Run one question through the MCP server + Gemini tool-calling loop.

    `env` is passed to the server subprocess (defaults to a copy of this
    process's environment) so DATABASE_URL / MAX_ROWS / STATEMENT_TIMEOUT_MS
    reach it; useful for pointing the benchmark at a different DB per run
    without mutating the parent process's environment.
    """
    start = time.perf_counter()
    result = HarnessResult(question=question)

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT)],
        env=env if env is not None else dict(os.environ),
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_resp = await session.list_tools()

                caller = GeminiToolCaller(tools_resp.tools, model_name=model_name)
                caller.start(SYSTEM_INSTRUCTION)

                text, calls = caller.send(question)
                rounds = 0
                while calls and rounds < max_rounds:
                    rounds += 1
                    tool_results: list[tuple[str, Any]] = []
                    for call in calls:
                        t0 = time.perf_counter()
                        is_error = False
                        try:
                            call_result = await session.call_tool(
                                call.name, call.arguments
                            )
                            payload = _extract_tool_payload(call_result)
                            is_error = bool(call_result.isError) or (
                                isinstance(payload, dict) and "error" in payload
                            )
                        except Exception as e:  # noqa: BLE001 - surfaced to the model & caller
                            payload = {"error": f"{type(e).__name__}: {e}"}
                            is_error = True
                        duration_ms = (time.perf_counter() - t0) * 1000

                        result.tool_calls.append(
                            {
                                "tool": call.name,
                                "arguments": call.arguments,
                                "duration_ms": round(duration_ms, 2),
                                "is_error": is_error,
                                "result_preview": _preview(payload),
                            }
                        )

                        if call.name == "run_query" and not is_error and isinstance(payload, dict):
                            result.final_sql = call.arguments.get("sql")
                            result.columns = payload.get("columns", [])
                            result.rows = payload.get("rows", [])
                            result.row_count = payload.get("row_count", 0)

                        tool_results.append((call.name, payload))

                    text, calls = caller.send_tool_results(tool_results)

                result.answer_text = text
                if calls and rounds >= max_rounds:
                    result.error = (
                        f"Stopped after {max_rounds} tool-call rounds "
                        "without a final answer."
                    )
    except Exception as e:  # noqa: BLE001 - never let the harness crash the benchmark run
        result.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    result.latency_ms = round((time.perf_counter() - start) * 1000, 2)
    return result


def ask(question: str, **kwargs: Any) -> dict[str, Any]:
    """Synchronous convenience wrapper around ask_async, for evaluation
    scripts that aren't already async. Returns HarnessResult.to_dict()."""
    return asyncio.run(ask_async(question, **kwargs)).to_dict()


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "How many vehicles are currently available?"
    print(json.dumps(ask(q), indent=2, default=str))
