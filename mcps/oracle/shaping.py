"""Pure result-shaping helpers: DB values -> JSON-safe, context-window-safe dicts.

No oracledb / connection imports here, mirroring guards.py: everything is unit
testable without a database, and the MCP layer stays a thin orchestrator.
"""

import datetime
import decimal
import json

# Appended to a truncated cell so the model knows the value continues.
_TRUNCATION_NOTE = "...[truncated, {total} chars total]"


def serialize_value(value, max_cell_chars: int):
    """Convert one DB value to a JSON-safe value, truncating oversized text.

    With oracledb.defaults.fetch_lobs = False a CLOB arrives as an unbounded
    str -- a handful of those can blow the MCP client's context window, so
    long strings are cut at max_cell_chars with an explicit marker.
    """
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, bytes):
        value = value.hex()
    if isinstance(value, str) and len(value) > max_cell_chars:
        return value[:max_cell_chars] + _TRUNCATION_NOTE.format(total=len(value))
    return value


def dedupe_columns(names: list[str]) -> list[str]:
    """Suffix repeated column names so none is lost when rows become dicts.

    `SELECT a.id, b.id FROM a JOIN b ...` is valid SQL and extremely common in
    LLM-written joins, but both columns arrive named ID -- and a dict keyed by
    column name would keep only the last. The first occurrence keeps its name;
    later ones become ID_2, ID_3, ... so every projected column survives and
    the collision is visible to the caller rather than silent.
    """
    seen: dict[str, int] = {}
    result = []
    for name in names:
        seen[name] = seen.get(name, 0) + 1
        if seen[name] == 1:
            result.append(name)
            continue
        candidate = f"{name}_{seen[name]}"
        while candidate in seen:  # a real column already called ID_2
            seen[name] += 1
            candidate = f"{name}_{seen[name]}"
        seen[candidate] = 1
        result.append(candidate)
    return result


def rows_to_dicts(description, rows, max_cell_chars: int) -> list[dict]:
    """Zip a cursor description with fetched rows into serialized dicts."""
    columns = dedupe_columns([col[0] for col in description])
    return [
        {col: serialize_value(val, max_cell_chars) for col, val in zip(columns, row)}
        for row in rows
    ]


def cap_payload(rows: list[dict], max_response_chars: int) -> tuple[list[dict], int]:
    """Drop trailing rows until the JSON-serialized payload fits the cap.

    Returns (kept_rows, dropped_count). Row order is preserved; rows are only
    dropped from the end, so 'first N rows' semantics survive the cap.
    """
    budget = max_response_chars - 2  # enclosing brackets
    kept = []
    for row in rows:
        row_size = len(json.dumps(row, default=str)) + 2  # separator
        if budget - row_size < 0:
            break
        budget -= row_size
        kept.append(row)
    return kept, len(rows) - len(kept)
