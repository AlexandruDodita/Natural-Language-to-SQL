"""Pure parts of the execution layer: response shaping, error extraction and
the session statements used by the row-level-security layer."""

from __future__ import annotations

import datetime
import decimal

import pytest

from db import (
    HttpRunner,
    QueryResult,
    SessionContext,
    build_runners,
    extract_http_error,
    parse_sql_response,
    session_statements,
    to_jsonable,
)


class FakeSettings:
    sql_backend_url = "http://backend:8080"
    target_database_url = ""
    executor = "http"
    statement_timeout_ms = 5000


def test_parse_sql_response():
    result = parse_sql_response(
        {
            "columns": ["id", "make"],
            "rows": [[1, "Toyota"], [2, "Ford"]],
            "row_count": 2,
            "duration_ms": 1.25,
        }
    )
    assert result.columns == ["id", "make"]
    assert result.rows == [[1, "Toyota"], [2, "Ford"]]
    assert result.row_count == 2
    assert result.duration_ms == pytest.approx(1.25)


def test_parse_sql_response_handles_an_empty_body():
    result = parse_sql_response({})
    assert result == QueryResult()


@pytest.mark.parametrize(
    "body_json,body_text,expected",
    [
        ({"error": "column x does not exist"}, "", "column x does not exist"),
        ({"detail": "boom"}, "", "boom"),
        (None, "plain text failure", "plain text failure"),
        (None, "", "SQL backend returned HTTP 500"),
    ],
)
def test_extract_http_error(body_json, body_text, expected):
    assert extract_http_error(500, body_text, body_json) == expected


def test_session_statements_without_context():
    stmts = session_statements(None, 3000)
    assert stmts[0][0] == "SET LOCAL statement_timeout = 3000"
    assert stmts[1][0] == "SET LOCAL transaction_read_only = on"
    assert len(stmts) == 2


def test_session_statements_set_role_and_scope():
    stmts = session_statements(
        SessionContext(role="app_agent", location_id=4, user_id="a1"), 5000
    )
    sqls = [s for s, _ in stmts]
    assert 'SET LOCAL ROLE "app_agent"' in sqls
    assert any("app.location_id" in s for s in sqls)
    # values travel as bound parameters, not inside the statement text
    location_stmt = next(s for s in stmts if "app.location_id" in s[0])
    assert location_stmt[1] == ("4",)


def test_session_statements_reject_quote_injection_in_the_role():
    stmts = session_statements(SessionContext(role='x" ; DROP'), 1000)
    role_stmt = next(s for s, _ in stmts if "SET LOCAL ROLE" in s)
    assert role_stmt == 'SET LOCAL ROLE "x ; DROP"'


def test_role_is_applied_after_the_scope_is_set():
    """SET ROLE must come last: the GUC has to exist before RLS evaluates it."""
    stmts = session_statements(
        SessionContext(role="app_agent", location_id=1, user_id="u"), 5000
    )
    sqls = [s for s, _ in stmts]
    assert sqls.index('SET LOCAL ROLE "app_agent"') > sqls.index(
        "SELECT set_config('app.location_id', %s, true)"
    )


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        ("text", "text"),
        (3, 3),
        (decimal.Decimal("10.50"), "10.50"),
        (datetime.date(2024, 5, 1), "2024-05-01"),
        (datetime.datetime(2024, 5, 1, 12, 30), "2024-05-01 12:30:00"),
        ([1, decimal.Decimal("2")], [1, "2"]),
        ({"a": decimal.Decimal("1")}, {"a": "1"}),
    ],
)
def test_to_jsonable(value, expected):
    assert to_jsonable(value) == expected


def test_build_runners_defaults_to_http():
    runner, direct = build_runners(FakeSettings())
    assert isinstance(runner, HttpRunner)
    assert direct is None


def test_build_runners_adds_a_direct_runner_when_a_dsn_is_configured():
    class S(FakeSettings):
        target_database_url = "postgresql://u:p@host/db"

    runner, direct = build_runners(S())
    assert isinstance(runner, HttpRunner)  # execution still goes through HTTP
    assert direct is not None and direct.supports_explain


def test_build_runners_direct_executor():
    class S(FakeSettings):
        target_database_url = "postgresql://u:p@host/db"
        executor = "direct"

    runner, direct = build_runners(S())
    assert runner is direct
    assert runner.supports_session_context


def test_build_runners_direct_without_dsn_falls_back():
    class S(FakeSettings):
        executor = "direct"

    runner, direct = build_runners(S())
    assert isinstance(runner, HttpRunner)
    assert direct is None
