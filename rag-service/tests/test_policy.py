"""Authorization matrix for the AST-rewriting policy engine.

The tests check three things the thesis claims: that row scoping is *injected
into the tree* (with the alias the query uses, and inside subqueries), that
hidden columns are refused or projected away, and that context values can never
become SQL syntax.
"""

from __future__ import annotations

import re

import pytest
import sqlglot

from policy import PolicyEngine, UserContext


def norm(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip().lower()


@pytest.fixture()
def manager() -> UserContext:
    return UserContext(user_id="m1", role="manager")


@pytest.fixture()
def agent() -> UserContext:
    return UserContext(user_id="a1", role="agent", location_id=4)


@pytest.fixture()
def analyst() -> UserContext:
    return UserContext(user_id="an1", role="analyst")


# ---------------------------------------------------------------------------
# Manager: nothing is rewritten
# ---------------------------------------------------------------------------
def test_manager_query_is_unchanged(policy_engine, manager):
    sql = "SELECT first_name, salary FROM employees LIMIT 10"
    result = policy_engine.rewrite(sql, manager)
    assert result.ok
    assert result.applied_filters == []
    assert "where" not in norm(result.sql)
    assert "salary" in norm(result.sql)


# ---------------------------------------------------------------------------
# Agent: row scoping
# ---------------------------------------------------------------------------
def test_agent_gets_a_location_predicate(policy_engine, agent):
    result = policy_engine.rewrite("SELECT id, make FROM vehicles", agent)
    assert result.ok
    assert "vehicles.location_id = 4" in norm(result.sql)
    assert [f["table"] for f in result.applied_filters] == ["vehicles"]


def test_predicate_uses_the_query_alias(policy_engine, agent):
    result = policy_engine.rewrite("SELECT v.id FROM vehicles AS v", agent)
    assert result.ok
    assert "v.location_id = 4" in norm(result.sql)
    assert "vehicles.location_id" not in norm(result.sql)


def test_existing_where_is_preserved_and_anded(policy_engine, agent):
    result = policy_engine.rewrite(
        "SELECT id FROM vehicles WHERE status = 'available'", agent
    )
    assert result.ok
    lowered = norm(result.sql)
    assert "status = 'available'" in lowered
    assert "location_id = 4" in lowered
    assert " and " in lowered


def test_every_scoped_table_in_a_join_is_filtered(policy_engine, agent):
    sql = (
        "SELECT r.id, v.make FROM reservations r "
        "JOIN vehicles v ON v.id = r.vehicle_id"
    )
    result = policy_engine.rewrite(sql, agent)
    assert result.ok
    lowered = norm(result.sql)
    assert "r.pickup_location = 4" in lowered
    assert "v.location_id = 4" in lowered
    assert {f["table"] for f in result.applied_filters} == {"reservations", "vehicles"}


def test_subqueries_are_scoped_too(policy_engine, agent):
    sql = (
        "SELECT c.first_name FROM clients c WHERE c.id IN "
        "(SELECT r.client_id FROM reservations r WHERE r.status = 'completed')"
    )
    result = policy_engine.rewrite(sql, agent)
    assert result.ok
    lowered = norm(result.sql)
    # the inner reservations scope got its own predicate
    assert "r.pickup_location = 4" in lowered
    # and the outer clients scope got the client-visibility subquery
    assert "c.id in (select" in lowered


def test_unscoped_tables_are_left_alone(policy_engine, agent):
    result = policy_engine.rewrite("SELECT name FROM vehicle_categories", agent)
    assert result.ok
    assert result.applied_filters == []


def test_rewritten_sql_still_parses(policy_engine, agent):
    result = policy_engine.rewrite(
        "SELECT COUNT(*) FROM reservations r JOIN clients c ON c.id = r.client_id",
        agent,
    )
    assert result.ok
    assert sqlglot.parse_one(result.sql, dialect="postgres") is not None


# ---------------------------------------------------------------------------
# Column denial
# ---------------------------------------------------------------------------
def test_agent_cannot_read_salary(policy_engine, agent):
    result = policy_engine.rewrite("SELECT e.salary FROM employees e", agent)
    assert not result.ok
    assert "salary" in (result.blocked_reason or "")


def test_unqualified_denied_column_is_also_blocked(policy_engine, agent):
    result = policy_engine.rewrite("SELECT salary FROM employees", agent)
    assert not result.ok


def test_denied_column_in_where_is_blocked(policy_engine, agent):
    result = policy_engine.rewrite(
        "SELECT first_name FROM employees WHERE salary > 5000", agent
    )
    assert not result.ok


def test_denied_column_in_aggregate_is_blocked(policy_engine, agent):
    result = policy_engine.rewrite("SELECT AVG(salary) FROM employees", agent)
    assert not result.ok


def test_star_is_expanded_to_allowed_columns(policy_engine, agent):
    result = policy_engine.rewrite("SELECT * FROM employees e", agent)
    assert result.ok, result.blocked_reason
    lowered = norm(result.sql)
    assert "salary" not in lowered
    assert "first_name" in lowered
    assert "e.location_id = 4" in lowered
    assert result.expanded_stars == ["employees"]


def test_star_on_an_unrestricted_table_is_untouched(policy_engine, agent):
    result = policy_engine.rewrite("SELECT * FROM vehicles v", agent)
    assert result.ok
    assert "*" in result.sql
    assert result.expanded_stars == []


def test_analyst_cannot_read_client_pii(policy_engine, analyst):
    blocked = policy_engine.rewrite("SELECT email FROM clients", analyst)
    assert not blocked.ok
    assert "email" in (blocked.blocked_reason or "")


def test_analyst_sees_company_wide_rows(policy_engine, analyst):
    result = policy_engine.rewrite("SELECT COUNT(*) FROM reservations", analyst)
    assert result.ok
    assert result.applied_filters == []


def test_auditor_cannot_touch_the_employees_table(policy_engine):
    ctx = UserContext(user_id="x", role="auditor")
    result = policy_engine.rewrite("SELECT id FROM employees", ctx)
    assert not result.ok
    assert "employees" in (result.blocked_reason or "")


# ---------------------------------------------------------------------------
# Fail-closed behaviour
# ---------------------------------------------------------------------------
def test_agent_without_a_location_is_refused(policy_engine):
    ctx = UserContext(user_id="a2", role="agent", location_id=None)
    result = policy_engine.rewrite("SELECT id FROM vehicles", ctx)
    assert not result.ok
    assert "location_id" in (result.blocked_reason or "")


def test_unknown_role_falls_back_to_the_default_role(policy_engine):
    ctx = UserContext(user_id="zz", role="does-not-exist")
    result = policy_engine.rewrite("SELECT id FROM vehicles", ctx)
    assert result.ok
    assert result.role == policy_engine.default_role


def test_db_role_is_exposed_for_the_rls_layer(policy_engine, agent, manager):
    assert policy_engine.db_role(agent) == "app_agent"
    assert policy_engine.db_role(manager) == "app_manager"
    assert policy_engine.max_rows(agent) == 200


# ---------------------------------------------------------------------------
# Injection safety: context values become literals, never syntax
# ---------------------------------------------------------------------------
INJECTION_POLICY = {
    "default_role": "tenant",
    "roles": {
        "tenant": {
            "requires": ["tenant"],
            "row_filters": {"clients": "clients.first_name = :tenant"},
        }
    },
}


def test_context_values_cannot_inject_sql(catalog):
    engine = PolicyEngine(INJECTION_POLICY, catalog=catalog)
    ctx = UserContext(
        user_id="u", role="tenant", attributes={"tenant": "x' OR '1'='1"}
    )
    result = engine.rewrite("SELECT id FROM clients", ctx)
    assert result.ok
    # the payload survives as a single quoted literal, not as SQL
    assert "'x'' OR ''1''=''1'" in result.sql
    tree = sqlglot.parse_one(result.sql, dialect="postgres")
    assert tree.sql(dialect="postgres") == result.sql


def test_numeric_context_values_stay_numeric(catalog):
    engine = PolicyEngine(
        {
            "default_role": "t",
            "roles": {"t": {"row_filters": {"vehicles": "vehicles.location_id = :location_id"}}},
        },
        catalog=catalog,
    )
    ctx = UserContext(user_id="u", role="t", location_id=7)
    result = engine.rewrite("SELECT id FROM vehicles", ctx)
    assert "location_id = 7" in norm(result.sql)
    assert "'7'" not in result.sql
