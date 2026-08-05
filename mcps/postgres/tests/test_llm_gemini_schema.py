"""
Pure tests for llm_gemini._sanitize_schema / mcp_tools_to_gemini_tool — the
JSON-Schema-to-genai-proto-Schema bridge. No network / API key required:
these only exercise local protobuf construction, never call the Gemini API.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import google.generativeai as genai  # noqa: E402

from llm_gemini import _sanitize_schema, mcp_tools_to_gemini_tool  # noqa: E402


def test_empty_schema_becomes_empty_object():
    assert _sanitize_schema(None) == {"type_": "OBJECT", "properties": {}}
    assert _sanitize_schema({}) == {"type_": "OBJECT", "properties": {}}


def test_drops_unknown_json_schema_keywords():
    # This is exactly what FastMCP emits for a `def f(table_name: str)` tool:
    # a "title" key the genai proto Schema has no field for.
    schema = {
        "properties": {"table_name": {"title": "Table Name", "type": "string"}},
        "required": ["table_name"],
        "title": "describe_tableArguments",
        "type": "object",
    }
    out = _sanitize_schema(schema)
    assert out == {
        "type_": "OBJECT",
        "properties": {"table_name": {"type_": "STRING"}},
        "required": ["table_name"],
    }
    # must not raise when handed to the real proto constructor
    genai.protos.Schema(**out)


def test_no_args_tool_schema():
    schema = {"properties": {}, "title": "list_tablesArguments", "type": "object"}
    out = _sanitize_schema(schema)
    assert out == {"type_": "OBJECT", "properties": {}}
    genai.protos.Schema(**out)


def test_optional_anyof_picks_non_null_branch():
    # pydantic v2 sometimes renders Optional[int] as anyOf[{type: integer}, {type: null}]
    schema = {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None}
    out = _sanitize_schema(schema)
    assert out["type_"] == "INTEGER"


def test_array_of_strings():
    schema = {"type": "array", "items": {"type": "string"}}
    out = _sanitize_schema(schema)
    assert out == {"type_": "ARRAY", "items": {"type_": "STRING"}}
    genai.protos.Schema(**out)


def test_mcp_tools_to_gemini_tool_builds_function_declarations():
    fake_tools = [
        SimpleNamespace(
            name="run_query",
            description="Run a SQL query.",
            inputSchema={
                "properties": {"sql": {"title": "Sql", "type": "string"}},
                "required": ["sql"],
                "title": "run_queryArguments",
                "type": "object",
            },
        ),
        SimpleNamespace(
            name="list_tables",
            description="List tables.",
            inputSchema={"properties": {}, "title": "list_tablesArguments", "type": "object"},
        ),
    ]
    tool = mcp_tools_to_gemini_tool(fake_tools)
    names = [fd.name for fd in tool.function_declarations]
    assert names == ["run_query", "list_tables"]
