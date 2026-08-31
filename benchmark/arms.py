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
import os
import pathlib
import re
import sys
import time
from typing import Callable, Optional

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

import clients  # noqa: E402

NAIVE_PROMPT = """You are a SQL expert for {domain}.

{schema}

Write a single PostgreSQL SELECT query answering the user's question.
Respond with ONLY the SQL. No markdown fences, no explanation.
If the question cannot be answered from this schema, respond with exactly: NO_SQL
"""


_FENCE_RE = re.compile(r"```[a-zA-Z]*\n(.*?)```", re.DOTALL)


def _strip_fences(text: str) -> str:
    """Recover the SQL from whatever wrapping the model put around it.

    Every arm's prompt asks for bare SQL and no fences, and the hosted models
    comply, so for them this is a no-op. Reasoning-tuned local models are the
    reason it has to do more: Arctic-Text2SQL-R1 narrates its derivation and
    then puts the finished query in a trailing ```sql block, and reading that
    whole narration as the prediction scores a model 0% for a query it in fact
    got right. Taking the LAST fenced block is what makes the local rows
    measure SQL quality rather than instruction-following on output format.

    The two shapes the hosted arms actually produce - bare SQL, and one fenced
    block that is the entire reply - both come back byte-identical to what the
    previous leading-fence-only version returned, so no hosted number moves.
    """
    t = text.strip()
    blocks = _FENCE_RE.findall(t)
    if blocks:
        return blocks[-1].strip()
    if t.startswith("```"):
        # An unterminated fence: the reply was cut off at the token limit.
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
        # A reply the server cut off at max_tokens is not a refusal, and it is
        # certainly not the model recognising an ambiguous question. Local
        # reasoning models hit the cap often enough that conflating the two put
        # six truncated Qwen3.5-9B answers into the ambiguity column, which
        # flattered a metric the thesis actually argues from. Truncation gets
        # its own name, and is left out of `clarified` entirely.
        truncated = bool(usage and usage.finish_reason == "length")
        return {
            "sql": None if no_sql else sql,
            # The naive arm has no notion of asking a question back; refusing to
            # emit SQL is the closest thing it has to recognising ambiguity, and
            # scoring it as such is generous to the baseline rather than unfair.
            "clarified": no_sql and not err and not truncated,
            "latency_ms": round(dt, 1),
            "error": err or ("output truncated at max_tokens" if truncated
                             and no_sql else None),
            "usage": usage.as_dict() if usage else None,
            "extra": {"prompt_chars": len(prompt), "truncated": truncated},
        }

    return run


DEFAULT_DOMAIN = "a car rental company database"


def make_naive_arm(schema_text: str, domain: str = DEFAULT_DOMAIN) -> Callable[[dict], dict]:
    prompt = NAIVE_PROMPT.format(schema=schema_text, domain=domain)
    return _single_shot_arm(prompt, clients.gemini_complete)


def make_local_arm(
    schema_text: str,
    base_url: str = clients.DEFAULT_LOCAL_BASE_URL,
    model: str = clients.DEFAULT_LOCAL_MODEL,
    domain: str = DEFAULT_DOMAIN,
) -> Callable[[dict], dict]:
    """The naive arm, answered by a model running on this machine.

    Any OpenAI-compatible server will do (llama.cpp's llama-server, LM Studio,
    vLLM, Ollama); the arm only needs `POST {base_url}/chat/completions`.
    """
    prompt = NAIVE_PROMPT.format(schema=schema_text, domain=domain)
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


CLI_AGENT_INSTRUCTION = """\
You are a careful data analyst answering one question about a PostgreSQL \
database for {domain}, using only the postgres MCP tools provided: \
list_tables, describe_table, get_schema, run_query.

Rules:
- Before writing SQL, call get_schema() (or list_tables()/describe_table()) so
  you know the real table and column names. Never guess at schema.
- Only SELECT (or WITH ... SELECT) statements are permitted.
- Your last tool call must be run_query, with SQL that fully answers the
  question.
- If the question is genuinely ambiguous -- more than one defensible reading
  that would give different numbers -- do NOT guess. Reply with your question
  back to the user and do not emit a FINAL_SQL line.
- Otherwise, end your reply with the exact SQL you ran on its own final line,
  formatted as:  FINAL_SQL: <the full SQL on one line>

Question: {question}
"""


def _cli_agent_arm(cmd_for, parse_out, model: str, domain: str,
                   timeout_s: float) -> Callable[[dict], dict]:
    """An agent driven through a coding-CLI in headless mode.

    Distinct from every other arm in this file: the model is not sent a schema
    and does not answer in one shot, it explores the live database through MCP
    tools and decides for itself when it knows enough. That is what makes it an
    agent rather than a translator, and it is why the arm cannot reuse
    `_single_shot_arm`.

    The CLI is driven as a subprocess rather than through an SDK because the
    credentials live in the CLI's own session -- there is no API key on this
    machine -- and because the thing being measured is the agent as shipped,
    default system prompt and all. That overhead is real and is reported: these
    runs carry a large cached prefix the leaner arms do not have, so read their
    cost against the other agentic arm (`mcp-postgres`), not against `naive`.
    """
    import subprocess

    def run(q: dict) -> dict:
        prompt = CLI_AGENT_INSTRUCTION.format(domain=domain, question=q["question"])
        t0 = time.perf_counter()
        try:
            proc = subprocess.run(cmd_for(prompt, model), capture_output=True,
                                  text=True, timeout=timeout_s, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return {"sql": None, "clarified": False,
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                    "error": f"timeout after {timeout_s}s", "usage": None, "extra": {}}
        dt = round((time.perf_counter() - t0) * 1000, 1)
        if proc.returncode != 0:
            return {"sql": None, "clarified": False, "latency_ms": dt,
                    "error": f"exit {proc.returncode}: {proc.stderr.strip()[:200]}",
                    "usage": None, "extra": {}}
        try:
            text, usage, extra = parse_out(proc.stdout)
        except Exception as e:
            return {"sql": None, "clarified": False, "latency_ms": dt,
                    "error": f"unparseable CLI output: {type(e).__name__}: {e}",
                    "usage": None, "extra": {}}

        m = re.search(r"FINAL_SQL:\s*(.+?)\s*$", text, re.S | re.M)
        sql = _strip_fences(m.group(1)) if m else None
        if sql:
            # The model sometimes keeps talking after the SQL; the query is the
            # part up to the first blank line.
            sql = sql.split("\n\n")[0].strip().rstrip(";")
        if usage is not None and not usage.latency_ms:
            # Codex reports no timing of its own; the wall clock this arm
            # measured is the only latency figure, and tokens/sec has to be
            # derived from it or the throughput column is empty for that model.
            usage.latency_ms = dt
            usage.tokens_per_sec = _rate_or_none(usage.output_tokens, dt)
        return {
            "sql": sql or None,
            # No SQL and no error means it answered with a question instead,
            # which is the behaviour the ambiguous questions score.
            "clarified": not sql,
            "latency_ms": dt,
            "error": None,
            "usage": usage.as_dict() if usage else None,
            "extra": extra,
        }

    return run


def _claude_cli_cmd(prompt: str, model: str) -> list[str]:
    cfg = REPO / "benchmark" / ".mcp-agent-config.json"
    tools = ",".join(f"mcp__postgres__{t}" for t in
                     ("list_tables", "describe_table", "get_schema", "run_query"))
    return ["claude", "-p", prompt, "--model", model, "--output-format", "json",
            "--mcp-config", str(cfg), "--strict-mcp-config", "--allowedTools", tools]


def _rate_or_none(tokens: int, ms: float):
    return round(tokens / (ms / 1000.0), 2) if tokens and ms and ms > 0 else None


def _claude_cli_parse(stdout: str):
    d = json.loads(stdout)
    u = d.get("usage") or {}
    # Claude reports output_tokens INCLUSIVE of thinking; Usage keeps the two
    # apart and re-adds them in its output_tokens property, so subtract here or
    # the reasoning tokens get counted twice.
    thinking = (u.get("output_tokens_details") or {}).get("thinking_tokens", 0) or 0
    out_total = u.get("output_tokens", 0) or 0
    # An agent's prompt cost is dominated by cached prefix reads, which are
    # billed at a fraction of the input rate. Summing the three into one
    # prompt_tokens keeps the token record honest, but it makes the per-token
    # cost extrapolation in cost_block wrong for this arm -- the CLI reports the
    # real, cache-aware figure, so that is what gets recorded in extra.
    latency = d.get("duration_ms") or 0.0
    usage = clients.Usage(
        prompt_tokens=(u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                       + u.get("cache_creation_input_tokens", 0)),
        completion_tokens=max(out_total - thinking, 0),
        thinking_tokens=thinking,
        latency_ms=latency,
        ttft_ms=d.get("ttft_ms"),
        tokens_per_sec=_rate_or_none(out_total, latency),
        finish_reason=d.get("stop_reason"),
    )
    usage.total_tokens = usage.prompt_tokens + out_total
    extra = {"turns": d.get("num_turns"), "cost_usd": d.get("total_cost_usd"),
             "cache_read_tokens": u.get("cache_read_input_tokens", 0),
             "permission_denials": len(d.get("permission_denials") or [])}
    return d.get("result") or "", usage, extra


def make_claude_agent_arm(model: str, domain: str, timeout_s: float = 600.0):
    return _cli_agent_arm(_claude_cli_cmd, _claude_cli_parse, model, domain, timeout_s)


# Codex refuses MCP tool calls in headless mode unless approvals and the
# sandbox are both bypassed -- an upstream limitation (openai/codex#24135); the
# documented `default_tools_approval_mode` and per-server `approval_mode` keys
# do not work on 0.151.0, both were tried. The bypass is therefore required to
# run this arm at all, and it is scoped as tightly as it can be: codex is
# pointed at an empty scratch directory rather than the repository, so an
# unsandboxed shell has nothing of the project in reach, and the MCP server
# refuses anything that is not a SELECT.
CODEX_JAIL = pathlib.Path(os.environ.get(
    "CODEX_JAIL", "/tmp/codex-benchmark-jail"))


def _codex_cli_cmd(prompt: str, model: str) -> list[str]:
    CODEX_JAIL.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((REPO / "benchmark" / ".mcp-agent-config.json").read_text())
    srv = cfg["mcpServers"]["postgres"]
    env_toml = ",".join(f'{k}="{v}"' for k, v in srv["env"].items())
    args_toml = ",".join(f'"{a}"' for a in srv["args"])
    return [
        "codex", "exec", "-m", model,
        "--dangerously-bypass-approvals-and-sandbox",
        "--cd", str(CODEX_JAIL), "--skip-git-repo-check", "--json",
        "-c", f'mcp_servers.postgres.command="{srv["command"]}"',
        "-c", f"mcp_servers.postgres.args=[{args_toml}]",
        "-c", f"mcp_servers.postgres.env={{{env_toml}}}",
        prompt,
    ]


def _codex_cli_parse(stdout: str):
    """Codex streams JSONL; the answer is the last agent_message it emitted."""
    text, usage_raw, tool_calls = "", {}, 0
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        item = ev.get("item") or {}
        if ev.get("type") == "item.completed":
            if item.get("type") == "agent_message":
                text = item.get("text") or text
            elif item.get("type") == "mcp_tool_call":
                tool_calls += 1
        elif ev.get("type") == "turn.completed":
            usage_raw = ev.get("usage") or {}
    reasoning = usage_raw.get("reasoning_output_tokens", 0) or 0
    out_total = usage_raw.get("output_tokens", 0) or 0
    usage = clients.Usage(
        prompt_tokens=usage_raw.get("input_tokens", 0) or 0,
        completion_tokens=max(out_total - reasoning, 0),
        thinking_tokens=reasoning,
    )
    usage.total_tokens = usage.prompt_tokens + out_total
    return text, usage, {"tool_calls": tool_calls,
                         "cached_input_tokens": usage_raw.get("cached_input_tokens", 0)}


def make_codex_agent_arm(model: str, domain: str, timeout_s: float = 600.0):
    return _cli_agent_arm(_codex_cli_cmd, _codex_cli_parse, model, domain, timeout_s)


REGISTRY = {
    "naive": make_naive_arm,
    "local": make_local_arm,
    "pipeline": make_pipeline_arm,
    "mcp-postgres": make_mcp_postgres_arm,
    "claude-agent": make_claude_agent_arm,
    "codex-agent": make_codex_agent_arm,
}
