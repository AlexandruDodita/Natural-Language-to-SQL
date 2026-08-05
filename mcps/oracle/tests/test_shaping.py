import datetime
import decimal
import inspect
import json
import sys

import shaping


# --------------------------------------------------------------------------
# serialize_value.
# --------------------------------------------------------------------------
def test_serialize_datetime_and_date():
    assert (
        shaping.serialize_value(datetime.datetime(2026, 7, 13, 8, 30), 2000)
        == "2026-07-13T08:30:00"
    )
    assert shaping.serialize_value(datetime.date(2026, 7, 13), 2000) == "2026-07-13"


def test_serialize_decimal_to_float():
    result = shaping.serialize_value(decimal.Decimal("12.50"), 2000)
    assert result == 12.5
    assert isinstance(result, float)


def test_serialize_bytes_to_hex():
    assert shaping.serialize_value(b"\xde\xad", 2000) == "dead"


def test_serialize_passes_through_scalars():
    assert shaping.serialize_value(None, 2000) is None
    assert shaping.serialize_value(42, 2000) == 42
    assert shaping.serialize_value("short", 2000) == "short"


def test_serialize_truncates_long_strings_with_marker():
    value = "x" * 5000
    result = shaping.serialize_value(value, 100)
    assert result.startswith("x" * 100)
    assert "truncated, 5000 chars total" in result
    assert len(result) < 200


def test_serialize_string_at_exact_limit_is_untouched():
    value = "x" * 100
    assert shaping.serialize_value(value, 100) == value


# --------------------------------------------------------------------------
# rows_to_dicts.
# --------------------------------------------------------------------------
def test_rows_to_dicts_zips_description_and_serializes():
    description = [("ID", None), ("PAID_AT", None)]
    rows = [(1, datetime.date(2026, 1, 2)), (2, None)]
    assert shaping.rows_to_dicts(description, rows, 2000) == [
        {"ID": 1, "PAID_AT": "2026-01-02"},
        {"ID": 2, "PAID_AT": None},
    ]


# --------------------------------------------------------------------------
# dedupe_columns -- `SELECT a.id, b.id` is valid SQL; neither column may be
# silently dropped when the row becomes a dict.
# --------------------------------------------------------------------------
def test_dedupe_columns_leaves_unique_names_alone():
    assert shaping.dedupe_columns(["ID", "NAME"]) == ["ID", "NAME"]


def test_dedupe_columns_suffixes_repeats_in_order():
    assert shaping.dedupe_columns(["ID", "ID", "ID"]) == ["ID", "ID_2", "ID_3"]


def test_dedupe_columns_avoids_colliding_with_a_real_column():
    # A genuine column already named ID_2 must not be clobbered by the suffix.
    assert shaping.dedupe_columns(["ID", "ID_2", "ID"]) == ["ID", "ID_2", "ID_3"]


def test_rows_to_dicts_preserves_every_duplicate_column():
    description = [("ID", None), ("ID", None), ("AMOUNT", None)]
    rows = [(111, 222, 65.0)]
    assert shaping.rows_to_dicts(description, rows, 2000) == [
        {"ID": 111, "ID_2": 222, "AMOUNT": 65.0}
    ]


# --------------------------------------------------------------------------
# cap_payload.
# --------------------------------------------------------------------------
def test_cap_payload_keeps_everything_under_cap():
    rows = [{"A": 1}, {"A": 2}]
    kept, dropped = shaping.cap_payload(rows, 1_000_000)
    assert kept == rows
    assert dropped == 0


def test_cap_payload_drops_trailing_rows_and_preserves_order():
    rows = [{"A": i, "PAD": "x" * 100} for i in range(50)]
    row_size = len(json.dumps(rows[0]))
    cap = row_size * 10  # room for fewer than 10 rows once separators count
    kept, dropped = shaping.cap_payload(rows, cap)
    assert 0 < len(kept) < 50
    assert dropped == 50 - len(kept)
    assert kept == rows[: len(kept)]
    assert len(json.dumps(kept)) <= cap


def test_cap_payload_empty_rows():
    kept, dropped = shaping.cap_payload([], 100)
    assert kept == []
    assert dropped == 0


def test_cap_payload_first_row_alone_over_cap_drops_all():
    rows = [{"BIG": "x" * 500}]
    kept, dropped = shaping.cap_payload(rows, 50)
    assert kept == []
    assert dropped == 1


# --------------------------------------------------------------------------
# shaping must stay a pure, DB-free module (same rule as guards).
# --------------------------------------------------------------------------
def test_shaping_module_never_imports_oracledb():
    source = inspect.getsource(shaping)
    assert "import oracledb" not in source
    assert "oracle_conn" not in source


def test_test_process_never_loaded_the_db_layer():
    assert "oracledb" not in sys.modules
    assert "oracle_conn" not in sys.modules
    assert "mcp_server" not in sys.modules
