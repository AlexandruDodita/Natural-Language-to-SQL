"""
Pure, DB-independent tests for db.validate_readonly_sql — the sqlglot-based
statement-type guard that run_query() applies before any SQL reaches
Postgres. No database connection is used or required.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db  # noqa: E402


ACCEPTED = [
    "SELECT * FROM vehicles",
    "  select * from vehicles;  ",
    "SELECT * FROM vehicles;",
    "WITH recent AS (SELECT * FROM reservations WHERE pickup_date > '2025-01-01') "
    "SELECT * FROM recent",
    "SELECT * FROM vehicles UNION SELECT * FROM vehicles",
    "SELECT * FROM vehicles INTERSECT SELECT * FROM vehicles",
    "SELECT * FROM vehicles EXCEPT SELECT * FROM vehicles",
    "SELECT count(*) FROM vehicles WHERE status = 'available'",
    "SELECT * FROM vehicles LIMIT 5",
    "SELECT v.make, c.name FROM vehicles v JOIN vehicle_categories c "
    "ON v.category_id = c.id",
]

REJECTED = [
    ("SELECT * FROM vehicles; DROP TABLE vehicles;", "single"),
    ("SELECT 1; SELECT 2;", "single"),
    ("DELETE FROM vehicles", "SELECT statements"),
    ("UPDATE vehicles SET status='retired'", "SELECT statements"),
    ("INSERT INTO vehicles (id) VALUES (1)", "SELECT statements"),
    ("DROP TABLE vehicles", "SELECT statements"),
    ("TRUNCATE vehicles", "SELECT statements"),
    ("GRANT SELECT ON vehicles TO PUBLIC", "SELECT statements"),
    ("COPY vehicles TO STDOUT", "SELECT statements"),
    ("SELECT * INTO new_table FROM vehicles", "INTO"),
    ("SELECT * FROM vehicles FOR UPDATE", "Locking"),
    ("SELECT * FROM vehicles FOR SHARE", "Locking"),
    ("WITH x AS (DELETE FROM vehicles RETURNING *) SELECT * FROM x", "Disallowed"),
    ("WITH x AS (INSERT INTO vehicles (id) VALUES (1) RETURNING *) SELECT * FROM x", "Disallowed"),
    ("", "Empty"),
    ("   ", "Empty"),
    ("not sql at all $$ ;;;", None),  # just must raise, message content unconstrained
]


@pytest.mark.parametrize("sql", ACCEPTED)
def test_accepts_valid_readonly_sql(sql):
    stmt = db.validate_readonly_sql(sql)
    assert stmt is not None


@pytest.mark.parametrize("sql,expect_substring", REJECTED)
def test_rejects_unsafe_or_invalid_sql(sql, expect_substring):
    with pytest.raises(db.QueryValidationError) as exc_info:
        db.validate_readonly_sql(sql)
    if expect_substring:
        assert expect_substring.lower() in str(exc_info.value).lower()


def test_rejects_none_like_empty_after_strip():
    with pytest.raises(db.QueryValidationError):
        db.validate_readonly_sql("\n\t  \n")


def test_error_is_a_value_error_subclass():
    # so callers that only catch ValueError still work
    assert issubclass(db.QueryValidationError, ValueError)
