"""Accept/reject matrix for the sqlglot-based validator.

This is the layer that stands between a hallucinated query and the database, so
it is tested as a matrix rather than with a few happy paths.
"""

from __future__ import annotations

import pytest

from validator import SqlValidator

TABLES = [
    "locations",
    "employees",
    "vehicle_categories",
    "vehicles",
    "clients",
    "reservations",
    "payments",
    "maintenance_records",
    "reviews",
]


@pytest.fixture()
def validator() -> SqlValidator:
    return SqlValidator(dialect="postgres", max_rows=200, known_tables=TABLES)


# ---------------------------------------------------------------------------
# Accepted queries
# ---------------------------------------------------------------------------
ACCEPTED = [
    ("simple select", "SELECT id, make FROM vehicles"),
    ("with limit", "SELECT id FROM vehicles LIMIT 5"),
    (
        "join with aliases",
        "SELECT e.first_name, l.city FROM employees e "
        "JOIN locations l ON l.id = e.location_id",
    ),
    (
        "aggregate + group by",
        "SELECT location_id, AVG(salary) AS avg_salary FROM employees "
        "GROUP BY location_id ORDER BY avg_salary DESC",
    ),
    (
        "cte",
        "WITH totals AS (SELECT client_id, SUM(total_cost) AS spend "
        "FROM reservations GROUP BY client_id) "
        "SELECT c.first_name, t.spend FROM totals t "
        "JOIN clients c ON c.id = t.client_id",
    ),
    (
        "union",
        "SELECT city FROM locations UNION SELECT make FROM vehicles",
    ),
    (
        "scalar subquery",
        "SELECT make FROM vehicles WHERE daily_rate > "
        "(SELECT AVG(daily_rate) FROM vehicles)",
    ),
    (
        "case expression",
        "SELECT CASE WHEN rating >= 4 THEN 'good' ELSE 'bad' END AS bucket, "
        "COUNT(*) FROM reviews GROUP BY 1",
    ),
    (
        "literal that looks like a keyword",
        "SELECT id FROM reservations WHERE status = 'cancelled' "
        "OR status = 'DELETE'",
    ),
    (
        "column whose name contains a keyword",
        "SELECT r.created_at AS update_time FROM reservations r",
    ),
    (
        "trailing semicolon",
        "SELECT COUNT(*) FROM clients;",
    ),
]


@pytest.mark.parametrize("label,sql", ACCEPTED, ids=[c[0] for c in ACCEPTED])
def test_accepts_read_only_queries(validator, label, sql):
    result = validator.validate(sql)
    assert result.ok, f"{label} should be accepted, got: {result.error}"
    assert result.sql


# ---------------------------------------------------------------------------
# Rejected queries
# ---------------------------------------------------------------------------
REJECTED = [
    ("empty", "", "Empty"),
    ("blank", "   ", "Empty"),
    ("insert", "INSERT INTO clients (first_name) VALUES ('x')", "Only SELECT"),
    ("update", "UPDATE employees SET salary = 1", "Only SELECT"),
    ("delete", "DELETE FROM reservations", "Only SELECT"),
    ("drop", "DROP TABLE clients", "Only SELECT"),
    ("create", "CREATE TABLE t (id int)", "Only SELECT"),
    ("alter", "ALTER TABLE clients ADD COLUMN x int", "Only SELECT"),
    ("truncate", "TRUNCATE clients", "Only SELECT"),
    ("grant", "GRANT SELECT ON clients TO public", "Only SELECT"),
    ("copy", "COPY clients TO '/tmp/out.csv'", "Only SELECT"),
    ("set", "SET ROLE postgres", "Only SELECT"),
    ("stacked statements", "SELECT 1; DROP TABLE clients", "Multiple"),
    (
        "stacked statements with select first",
        "SELECT id FROM clients; DELETE FROM clients",
        "Multiple",
    ),
    ("select into", "SELECT * INTO backup FROM clients", "Forbidden"),
    ("for update lock", "SELECT id FROM clients FOR UPDATE", "Forbidden"),
    ("pg_catalog", "SELECT * FROM pg_catalog.pg_user", "system catalog"),
    ("bare pg_ table", "SELECT * FROM pg_shadow", "system catalog"),
    (
        "information_schema",
        "SELECT table_name FROM information_schema.tables",
        "system catalog",
    ),
    ("pg_sleep", "SELECT pg_sleep(10)", "not allowed"),
    ("pg_read_file", "SELECT pg_read_file('/etc/passwd')", "not allowed"),
    ("dblink", "SELECT * FROM dblink('host=x', 'select 1') AS t(a int)", "not allowed"),
    ("set_config", "SELECT set_config('app.location_id', '9', false)", "not allowed"),
    ("unknown table", "SELECT * FROM salaries_2024", "Unknown table"),
    ("placeholder", "SELECT * FROM clients WHERE id = :id", "Forbidden"),
    (
        "nested dml in cte",
        "WITH x AS (DELETE FROM clients RETURNING id) SELECT * FROM x",
        "Forbidden",
    ),
]


@pytest.mark.parametrize(
    "label,sql,expected", REJECTED, ids=[c[0] for c in REJECTED]
)
def test_rejects_unsafe_queries(validator, label, sql, expected):
    result = validator.validate(sql)
    assert not result.ok, f"{label} should have been rejected"
    assert expected.lower() in (result.error or "").lower(), (
        f"{label}: unexpected error message {result.error!r}"
    )


# ---------------------------------------------------------------------------
# Row cap
# ---------------------------------------------------------------------------
def test_limit_is_injected_when_missing(validator):
    result = validator.validate("SELECT id FROM vehicles")
    assert result.limit_applied == 200
    assert "LIMIT 200" in result.sql.upper()


def test_limit_is_clamped_when_too_large(validator):
    result = validator.validate("SELECT id FROM vehicles LIMIT 100000")
    assert result.limit_applied == 200
    assert "LIMIT 200" in result.sql.upper()
    assert "100000" not in result.sql


def test_smaller_limit_is_preserved(validator):
    result = validator.validate("SELECT id FROM vehicles LIMIT 5")
    assert result.limit_applied == 5
    assert "LIMIT 5" in result.sql.upper()


def test_limit_applies_to_set_operations(validator):
    result = validator.validate(
        "SELECT city FROM locations UNION SELECT make FROM vehicles"
    )
    assert result.ok
    assert "LIMIT 200" in result.sql.upper()


def test_role_specific_row_cap():
    strict = SqlValidator(dialect="postgres", max_rows=10, known_tables=TABLES)
    result = strict.validate("SELECT id FROM vehicles LIMIT 500")
    assert result.limit_applied == 10


# ---------------------------------------------------------------------------
# Table extraction and dialects
# ---------------------------------------------------------------------------
def test_reports_referenced_tables(validator):
    result = validator.validate(
        "SELECT r.id FROM reservations r "
        "JOIN vehicles v ON v.id = r.vehicle_id "
        "JOIN clients c ON c.id = r.client_id"
    )
    assert sorted(result.tables) == ["clients", "reservations", "vehicles"]


def test_cte_names_are_not_reported_as_tables(validator):
    result = validator.validate(
        "WITH recent AS (SELECT id FROM reservations) SELECT * FROM recent"
    )
    assert result.ok
    assert result.tables == ["reservations"]


def test_dialect_is_parameterised():
    oracle = SqlValidator(dialect="oracle", max_rows=50, enforce_known_tables=False)
    result = oracle.validate("SELECT sysdate FROM dual")
    assert result.ok, result.error
    assert "dual" in result.sql.lower()


def test_unknown_table_check_can_be_disabled():
    lenient = SqlValidator(
        dialect="postgres", max_rows=200, known_tables=TABLES,
        enforce_known_tables=False,
    )
    assert lenient.validate("SELECT * FROM some_other_table").ok
