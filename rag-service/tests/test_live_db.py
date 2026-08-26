"""Integration tests that need a live car_rental database.

Skipped unless TEST_DATABASE_URL is set, e.g.

    docker compose up -d test_app_db
    TEST_DATABASE_URL=postgresql://readonly_user:readonly_pass@localhost:5434/car_rental \
        pytest rag-service/tests -q

They cover the parts that cannot be faked: real introspection, the value index
built by sampling, EXPLAIN dry-runs, and the row-level-security policies of
``test_app_db/init/04_rls.sql``.
"""

from __future__ import annotations

import asyncio

import pytest

from db import DirectRunner, SessionContext, SqlExecutionError
from policy import UserContext
from retrieval import build_value_index
from schema_store import introspect

pytestmark = pytest.mark.live


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def runner(live_dsn) -> DirectRunner:
    return DirectRunner(live_dsn, statement_timeout_ms=5000)


# ---------------------------------------------------------------------------
# Introspection
# ---------------------------------------------------------------------------
def test_introspection_finds_the_whole_schema(runner):
    live = run(introspect(runner, ["public"]))
    assert {t.name for t in live.tables} == {
        "locations",
        "employees",
        "vehicle_categories",
        "vehicles",
        "clients",
        "reservations",
        "payments",
        "maintenance_records",
        "reviews",
    }
    vehicles = live.table("vehicles")
    assert vehicles.column("id").is_primary_key
    assert vehicles.column("license_plate").is_unique
    assert vehicles.column("location_id").references == "locations.id"
    assert "available" in vehicles.column("status").check


def test_committed_fixture_matches_the_live_schema(runner, catalog):
    live = run(introspect(runner, ["public"]))
    live_shape = {
        t.name: [(c.name, c.data_type) for c in t.columns] for t in live.tables
    }
    fixture_shape = {
        t.name: [(c.name, c.data_type) for c in t.columns] for t in catalog.tables
    }
    assert live_shape == fixture_shape


def test_value_index_samples_low_cardinality_columns(runner):
    live = run(introspect(runner, ["public"]))
    index = run(build_value_index(runner, live, max_distinct=60, sample_rows=5000))
    matches = {(m["table"], m["column"]) for m in index.lookup("Toyota cars in Miami")}
    assert ("vehicles", "make") in matches
    assert ("locations", "city") in matches
    # high-cardinality columns must not be indexed
    assert not any(
        ref.startswith("clients.email") for refs in index.entries.values() for ref in refs
    )


# ---------------------------------------------------------------------------
# Dry run and limits
# ---------------------------------------------------------------------------
def test_explain_rejects_an_unknown_column_without_executing(runner):
    with pytest.raises(SqlExecutionError) as exc:
        run(runner.explain("SELECT colour FROM vehicles"))
    assert "colour" in str(exc.value)


def test_explain_accepts_a_valid_query(runner):
    run(runner.explain("SELECT make FROM vehicles LIMIT 10"))


def test_statement_timeout_is_enforced(live_dsn):
    strict = DirectRunner(live_dsn, statement_timeout_ms=200)
    with pytest.raises(SqlExecutionError) as exc:
        run(strict.execute("SELECT pg_sleep(3)"))
    assert "timeout" in str(exc.value).lower()


def test_writes_are_refused_at_the_database_level(runner):
    with pytest.raises(SqlExecutionError):
        run(runner.execute("DELETE FROM reviews"))


# ---------------------------------------------------------------------------
# Row-level security (04_rls.sql)
# ---------------------------------------------------------------------------
def _count(runner, sql, session=None) -> int:
    return run(runner.execute(sql, session=session)).rows[0][0]


def test_readonly_user_is_unaffected_by_rls(runner):
    """Backwards compatibility: the existing execution path still sees everything."""
    assert _count(runner, "SELECT COUNT(*) FROM employees") > 0
    assert _count(runner, "SELECT COUNT(salary) FROM employees") > 0


def test_manager_role_sees_the_whole_company(runner):
    total = _count(runner, "SELECT COUNT(*) FROM vehicles")
    as_manager = _count(
        runner,
        "SELECT COUNT(*) FROM vehicles",
        SessionContext(role="app_manager", user_id="m"),
    )
    assert as_manager == total


def test_agent_role_only_sees_its_own_branch(runner):
    total = _count(runner, "SELECT COUNT(*) FROM vehicles")
    scoped = _count(
        runner,
        "SELECT COUNT(*) FROM vehicles",
        SessionContext(role="app_agent", location_id=1, user_id="a"),
    )
    assert 0 < scoped < total


def test_agent_scope_follows_the_session_variable(runner):
    first = _count(
        runner,
        "SELECT COUNT(*) FROM reservations",
        SessionContext(role="app_agent", location_id=1),
    )
    second = _count(
        runner,
        "SELECT COUNT(*) FROM reservations",
        SessionContext(role="app_agent", location_id=2),
    )
    assert first != second


def test_agent_without_a_location_sees_nothing(runner):
    assert (
        _count(
            runner, "SELECT COUNT(*) FROM vehicles", SessionContext(role="app_agent")
        )
        == 0
    )


def test_salary_is_refused_by_column_privileges(runner):
    with pytest.raises(SqlExecutionError) as exc:
        run(
            runner.execute(
                "SELECT AVG(salary) FROM employees",
                session=SessionContext(role="app_agent", location_id=1),
            )
        )
    assert "permission denied" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# The application policy and the database agree
# ---------------------------------------------------------------------------
def test_rewritten_query_runs_and_is_scoped(runner, policy_engine):
    ctx = UserContext(user_id="a", role="agent", location_id=1)
    rewritten = policy_engine.rewrite(
        "SELECT v.id, v.location_id FROM vehicles v LIMIT 200", ctx
    )
    assert rewritten.ok
    result = run(runner.execute(rewritten.sql))
    assert result.row_count > 0
    assert {row[1] for row in result.rows} == {1}


def test_application_and_database_layers_agree(runner, policy_engine):
    """The AST rewrite and the RLS policy must return the same rows."""
    ctx = UserContext(user_id="a", role="agent", location_id=3)
    rewritten = policy_engine.rewrite("SELECT COUNT(*) FROM reservations", ctx)
    app_layer = run(runner.execute(rewritten.sql)).rows[0][0]
    db_layer = _count(
        runner,
        "SELECT COUNT(*) FROM reservations",
        SessionContext(role="app_agent", location_id=3),
    )
    assert app_layer == db_layer
