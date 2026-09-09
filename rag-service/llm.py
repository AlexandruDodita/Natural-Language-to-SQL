"""LLM access and prompt construction.

``LLMClient`` is a two-method interface (``generate_json`` / ``stream_text``) so
the planned comparison between Gemini and a local model only needs a second
implementation of this class — the pipeline itself is provider agnostic.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterator, Optional, Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
SQL_INSTRUCTIONS = """You are a SQL expert answering questions over a PostgreSQL database.

Respond ONLY with a valid JSON object — no markdown, no explanation, no extra text.

If the question needs data:
{"sql": "SELECT ...", "reasoning": "one-line explanation", "chart": {"type": "bar|line|pie|area|none", "title": "Chart title", "x": "column_name_for_x_axis", "y": "column_name_for_y_axis"}}

If the question does NOT need data (greetings, small talk, general knowledge):
{"sql": null, "reasoning": "no data needed", "chart": null}
"""

CLARIFICATION_INSTRUCTIONS = """If the question is genuinely under-specified — that is, several
different SQL queries would be equally defensible and they would give different
answers (for example "who are the best clients?": by total spend, by number of
reservations, or by how long they have been customers) — do NOT guess. Return:
{"clarification": "a single short question that asks the user to pick an interpretation", "options": [{"label": "By total spend", "measure": "SUM(p.amount) WHERE p.status = 'completed'", "question": "the same question, rewritten so it states this reading"}], "sql": null, "chart": null}
Each option names one reading: `label` is what the user picks, `measure` is the
SQL expression that reading would aggregate on (so the choice is reproducible),
and `question` restates the original question unambiguously — it is sent back
verbatim when the user picks that option. Give two to four options.
Use this sparingly: only when the ambiguity changes the result, never for
questions that have one natural reading.
"""

CHART_RULES = """Chart rules:
- Set chart.type to "none" when the result is a single scalar, a list of text-only rows, or not meaningful as a visualization.
- Use "bar" for comparisons across categories.
- Use "line" for time-series or trends.
- Use "pie" for proportions (fewer than ~8 slices).
- Use "area" for cumulative or stacked time-series.
- x must be the column name used for labels/categories; y must be the column with numeric values.
- If multiple numeric columns exist, pick the most relevant one for y.
- The user may explicitly ask for a chart/report/export — always honour that request.
"""

SQL_RULES = """SQL rules:
- Use only the tables and columns listed above; never invent names.
- Always use table aliases in JOINs.
- Produce a single SELECT statement (CTEs are allowed). Never write INSERT, UPDATE, DELETE or any DDL.
- Do not query system catalogs (pg_catalog, information_schema).
- Limit results to {max_rows} rows unless the user asks for fewer.
"""

NO_DATA_ANSWER_PROMPT = """You are a helpful assistant for a car rental company.
No database query was run for this message.

CRITICAL: you have no data. Never state, estimate or invent any figure, name,
date or statistic about the company. If the question needs data you do not
have, say plainly that you cannot provide it and why. Otherwise answer
conversationally (greetings, what you can do, general knowledge).
"""

ANSWER_SYSTEM_PROMPT = """You are a helpful assistant for a car rental company.
You have access to live data from the company database.
Answer the user's question naturally and concisely based on the data provided.
If the data is a table, summarise the key findings rather than listing every row unless asked.
Format numbers clearly (e.g. currency with 2 decimal places).
Do NOT include, repeat, or show the SQL query in your response — only present the results in plain language.
"""

CLARIFY_ANSWER_PROMPT = """You are a helpful assistant for a car rental company.
The user's question is ambiguous. Ask them the following clarifying question in
natural language, briefly explaining the possible interpretations. Be concise
(two sentences at most) and do not invent data.
"""


def build_sql_prompt(
    schema_text: str,
    question: str,
    history_text: str = "",
    max_rows: int = 200,
    hidden_columns: Optional[list[str]] = None,
    allow_clarification: bool = True,
) -> str:
    parts = [SQL_INSTRUCTIONS]
    if allow_clarification:
        parts.append(CLARIFICATION_INSTRUCTIONS)
    parts.append("Database schema (only these tables are available):\n" + schema_text)
    if hidden_columns:
        parts.append(
            "The following columns are NOT readable by the current user; never "
            "reference them: " + ", ".join(hidden_columns) + ".\n"
            "If the question can only be answered with one of those columns, do "
            "not answer from memory and do not substitute another column. "
            'Return {"sql": null, "refusal": "short reason", "chart": null}.'
        )
    parts.append(CHART_RULES)
    parts.append(SQL_RULES.format(max_rows=max_rows))
    if history_text:
        parts.append("Recent conversation:\n" + history_text)
    parts.append(f"User question: {question}")
    return "\n\n".join(parts)


def build_repair_prompt(
    schema_text: str,
    question: str,
    failed_sql: str,
    error: str,
    stage: str,
    max_rows: int = 200,
) -> str:
    return "\n\n".join(
        [
            SQL_INSTRUCTIONS,
            "Database schema (only these tables are available):\n" + schema_text,
            CHART_RULES,
            SQL_RULES.format(max_rows=max_rows),
            f"User question: {question}",
            (
                "Your previous query failed during "
                f"{stage}:\n\n```sql\n{failed_sql}\n```\n\n"
                f"Database/validator error:\n{error}\n\n"
                "Rewrite the query so it fixes exactly this error. Check every "
                "table and column name against the schema above. Answer with the "
                "same JSON format as before."
            ),
        ]
    )


def build_answer_prompt(question: str, results_text: Optional[str]) -> str:
    if results_text:
        return (
            f"{ANSWER_SYSTEM_PROMPT}\n\n"
            f"The user asked: {question}\n\nDatabase results:\n{results_text}"
        )
    # No query was executed: the anti-fabrication prompt is what stops the model
    # from inventing plausible-looking figures.
    return f"{NO_DATA_ANSWER_PROMPT}\n\nThe user asked: {question}"


def build_clarification_prompt(question: str, clarification: str) -> str:
    return (
        f"{CLARIFY_ANSWER_PROMPT}\n\nUser question: {question}\n\n"
        f"Clarifying question to ask: {clarification}"
    )


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------
class LLMClient(Protocol):
    name: str

    def generate_json(self, prompt: str) -> dict: ...

    def stream_text(self, prompt: str, history: Optional[list[dict]] = None) -> Iterator[str]: ...


def parse_json_response(raw: str) -> dict:
    """Tolerant JSON extraction (models like wrapping answers in code fences)."""
    text = (raw or "").strip()
    if text.startswith("```"):
        chunks = text.split("```")
        text = chunks[1] if len(chunks) > 1 else text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if 0 <= start < end:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    raise ValueError(f"model did not return JSON: {raw[:200]}")


class GeminiClient:
    def __init__(self, api_key: str, model: str):
        import google.generativeai as genai

        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not configured")
        genai.configure(api_key=api_key)
        self.name = model
        self._model = genai.GenerativeModel(model)

    def generate_json(self, prompt: str) -> dict:
        chat = self._model.start_chat(history=[])
        response = chat.send_message(prompt)
        return parse_json_response(response.text or "")

    def stream_text(
        self, prompt: str, history: Optional[list[dict]] = None
    ) -> Iterator[str]:
        chat = self._model.start_chat(history=history or [])
        for chunk in chat.send_message(prompt, stream=True):
            if chunk.text:
                yield chunk.text


class UnavailableClient:
    """Used when no API key is configured: the service still starts and every
    non-LLM stage (introspection, retrieval, validation, policy) stays testable."""

    name = "unavailable"

    def generate_json(self, prompt: str) -> dict:
        raise RuntimeError("LLM is not configured (GEMINI_API_KEY missing)")

    def stream_text(
        self, prompt: str, history: Optional[list[dict]] = None
    ) -> Iterator[str]:
        raise RuntimeError("LLM is not configured (GEMINI_API_KEY missing)")


def build_client(settings) -> Any:
    try:
        return GeminiClient(settings.gemini_api_key, settings.gemini_model)
    except Exception as exc:
        logger.warning("LLM unavailable: %s", exc)
        return UnavailableClient()
