"""
llm_gemini.py — the ONLY module in this package that knows about a
specific LLM provider.

client_harness.py drives the tool-calling loop against generic
`ToolCallRequest` objects; it never touches google.generativeai directly.
That keeps the binding swappable — to plug in a local model later,
implement a class with the same three methods as GeminiToolCaller
(`start`, `send`, `send_tool_results`) and hand it to
`client_harness.ask_async(..., caller_factory=...)`.

Uses Gemini via `google-generativeai` with function calling, matching
rag-service/main.py's model choice (GEMINI_API_KEY / GEMINI_MODEL) so the
thesis's comparison between this baseline and the custom pipeline is on
the same underlying model.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Iterable

import google.generativeai as genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


# ---------------------------------------------------------------------------
# MCP JSON-Schema -> genai proto Schema conversion
# ---------------------------------------------------------------------------
#
# mcp.types.Tool.inputSchema is a standard JSON Schema dict (auto-generated
# by the MCP SDK from each tool function's signature via pydantic), e.g.:
#   {"type": "object", "properties": {"sql": {"title": "Sql", "type":
#    "string"}}, "required": ["sql"], "title": "run_queryArguments"}
#
# google-generativeai's genai.protos.Schema uses different field names
# ("type_" instead of "type", upper-cased enum values) and only understands
# a small fixed set of keys — it errors on unknown ones (e.g. "title"). This
# sanitizer bridges the two, silently dropping JSON-Schema keywords the
# proto doesn't model (title, default, additionalProperties, $defs, ...)
# instead of failing on them.


def _sanitize_schema(schema: dict[str, Any] | None) -> dict[str, Any]:
    if not schema:
        return {"type_": "OBJECT", "properties": {}}

    schema_type = schema.get("type")

    # pydantic v2 sometimes emits `Optional[X]` as {"anyOf": [{"type": X},
    # {"type": "null"}]} instead of a plain "type" key. Pick the first
    # non-null branch so we still produce a usable (if slightly lossy)
    # schema rather than erroring.
    if schema_type is None and ("anyOf" in schema or "oneOf" in schema):
        options = schema.get("anyOf") or schema.get("oneOf") or []
        non_null = [o for o in options if o.get("type") not in (None, "null")]
        schema = non_null[0] if non_null else {"type": "string"}
        schema_type = schema.get("type", "string")

    out: dict[str, Any] = {"type_": str(schema_type or "string").upper()}

    if schema.get("description"):
        out["description"] = schema["description"]
    if schema.get("enum"):
        out["enum"] = [str(v) for v in schema["enum"]]
    if schema_type == "array" and schema.get("items"):
        out["items"] = _sanitize_schema(schema["items"])
    if schema_type == "object":
        props = schema.get("properties") or {}
        out["properties"] = {k: _sanitize_schema(v) for k, v in props.items()}
        if schema.get("required"):
            out["required"] = list(schema["required"])

    return out


def mcp_tools_to_gemini_tool(mcp_tools: Iterable[Any]) -> "genai.protos.Tool":
    """Convert a list of `mcp.types.Tool` (from `ClientSession.list_tools()`)
    into a single `genai.protos.Tool` with one FunctionDeclaration each."""
    declarations = [
        genai.protos.FunctionDeclaration(
            name=tool.name,
            description=tool.description or "",
            parameters=_sanitize_schema(tool.inputSchema),
        )
        for tool in mcp_tools
    ]
    return genai.protos.Tool(function_declarations=declarations)


# ---------------------------------------------------------------------------
# Tool-calling session wrapper
# ---------------------------------------------------------------------------


@dataclass
class ToolCallRequest:
    name: str
    arguments: dict[str, Any]


class GeminiToolCaller:
    """Thin wrapper around a Gemini chat session with function calling.

    Interface a local-model replacement must implement:
      - `start(system_instruction: str) -> None`
      - `send(message: str) -> tuple[str, list[ToolCallRequest]]`
      - `send_tool_results(results: list[tuple[str, Any]]) ->
         tuple[str, list[ToolCallRequest]]`
    """

    def __init__(
        self,
        mcp_tools: Iterable[Any],
        model_name: str | None = None,
        api_key: str | None = None,
    ):
        api_key = api_key or GEMINI_API_KEY
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set (checked env var and constructor arg)."
            )
        genai.configure(api_key=api_key)
        self._model_name = model_name or GEMINI_MODEL
        self._tool = mcp_tools_to_gemini_tool(mcp_tools)
        self._chat = None

    def start(self, system_instruction: str) -> None:
        model = genai.GenerativeModel(
            self._model_name,
            tools=[self._tool],
            system_instruction=system_instruction,
        )
        self._chat = model.start_chat()

    def send(self, message: str) -> tuple[str, list[ToolCallRequest]]:
        if self._chat is None:
            raise RuntimeError("call start(system_instruction) before send()")
        response = self._chat.send_message(message)
        return self._parse_response(response)

    def send_tool_results(
        self, results: list[tuple[str, Any]]
    ) -> tuple[str, list[ToolCallRequest]]:
        if self._chat is None:
            raise RuntimeError("call start(system_instruction) before send_tool_results()")
        parts = [
            genai.protos.Part(
                function_response=genai.protos.FunctionResponse(
                    name=name, response={"result": payload}
                )
            )
            for name, payload in results
        ]
        response = self._chat.send_message(genai.protos.Content(parts=parts, role="user"))
        return self._parse_response(response)

    @staticmethod
    def _parse_response(response) -> tuple[str, list[ToolCallRequest]]:
        text_parts: list[str] = []
        calls: list[ToolCallRequest] = []
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return "", []
        for part in candidates[0].content.parts:
            text = getattr(part, "text", None)
            if text:
                text_parts.append(text)
            fc = getattr(part, "function_call", None)
            if fc and fc.name:
                calls.append(ToolCallRequest(name=fc.name, arguments=dict(fc.args)))
        return "\n".join(text_parts).strip(), calls
