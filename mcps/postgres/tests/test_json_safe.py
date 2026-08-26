"""
Pure tests for db._json_safe_value / _json_safe_row — the converters that
make Postgres result cells (Decimal, date/datetime, UUID, bytes) safe to
JSON-serialize over the MCP transport. No database connection required.
"""

import datetime
import decimal
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db  # noqa: E402


def test_decimal_becomes_float():
    assert db._json_safe_value(decimal.Decimal("19.99")) == 19.99
    assert isinstance(db._json_safe_value(decimal.Decimal("19.99")), float)


def test_date_becomes_isoformat_string():
    d = datetime.date(2025, 1, 15)
    assert db._json_safe_value(d) == "2025-01-15"


def test_datetime_becomes_isoformat_string():
    dt = datetime.datetime(2025, 1, 15, 10, 30, 0)
    assert db._json_safe_value(dt) == "2025-01-15T10:30:00"


def test_uuid_becomes_string():
    u = uuid.uuid4()
    assert db._json_safe_value(u) == str(u)


def test_bytes_become_hex_string():
    assert db._json_safe_value(b"\x01\x02") == "0102"


def test_plain_values_pass_through():
    assert db._json_safe_value(5) == 5
    assert db._json_safe_value("hello") == "hello"
    assert db._json_safe_value(None) is None
    assert db._json_safe_value(True) is True


def test_json_safe_row_converts_all_values():
    row = {
        "id": 1,
        "price": decimal.Decimal("42.50"),
        "created": datetime.date(2024, 6, 1),
        "name": "Civic",
    }
    safe = db._json_safe_row(row)
    assert safe == {
        "id": 1,
        "price": 42.5,
        "created": "2024-06-01",
        "name": "Civic",
    }
    # every value must now be trivially JSON-serializable
    import json

    json.dumps(safe)
