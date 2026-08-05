"""
db.py — connection, introspection, and query-execution logic for the
PostgreSQL MCP baseline server.

This module is deliberately free of any MCP or LLM imports. It can be used
directly (e.g. `import db; db.list_tables()`) without spinning up the MCP
stdio transport, which is what makes it usable both by server.py (the MCP
tool layer) and by test/benchmark code that wants to call the same logic
in-process.

Safety model (defense in depth):
  1. DB-level: connects as `readonly_user`, which only has SELECT grants
     (see test_app_db/init/03_readonly_user.sql).
  2. Session-level: every connection is opened with
     `default_transaction_read_only=on` and a `statement_timeout`, enforced
     server-side by Postgres itself.
  3. Statement-level: `run_query` parses the submitted SQL with sqlglot and
     rejects anything that isn't exactly one SELECT (or WITH ... SELECT)
     statement — including data-modifying CTEs, SELECT INTO, and locking
     reads (FOR UPDATE/SHARE) — before it is ever sent to Postgres.
  4. Result-level: rows are capped at `MAX_ROWS`.
"""

from __future__ import annotations

import dataclasses
import datetime
import decimal
import os
import time
import uuid
from typing import Any, Optional

import psycopg
import psycopg.errors
import psycopg.rows
import psycopg.sql
import sqlglot
from sqlglot import exp

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_DATABASE_URL = (
    "postgresql://readonly_user:readonly_pass@localhost:5434/car_rental"
)


@dataclasses.dataclass(frozen=True)
class Settings:
    database_url: str
    max_rows: int
    statement_timeout_ms: int
    sql_dialect: str = "postgres"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL),
            max_rows=int(os.environ.get("MAX_ROWS", "100")),
            statement_timeout_ms=int(os.environ.get("STATEMENT_TIMEOUT_MS", "5000")),
        )


SETTINGS = Settings.from_env()


class QueryValidationError(ValueError):
    """The submitted SQL failed the read-only / single-statement checks."""


class QueryExecutionError(RuntimeError):
    """A validated query failed to execute against the database."""


# ---------------------------------------------------------------------------
# JSON-safety helpers
# ---------------------------------------------------------------------------


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _json_safe_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: _json_safe_value(v) for k, v in row.items()}


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------


def get_connection(settings: Optional[Settings] = None) -> psycopg.Connection:
    """Open a short-lived, read-only, timeout-bounded connection.

    A fresh connection per call keeps this module simple and safe for both
    the low-concurrency MCP stdio server and the sequential evaluation
    harness. `statement_timeout` and `default_transaction_read_only` are set
    via connection options so they apply server-side, independent of
    anything the submitted SQL text does.
    """
    settings = settings or SETTINGS
    return psycopg.connect(
        settings.database_url,
        autocommit=True,
        row_factory=psycopg.rows.dict_row,
        options=(
            f"-c statement_timeout={settings.statement_timeout_ms} "
            "-c default_transaction_read_only=on"
        ),
    )


# ---------------------------------------------------------------------------
# Introspection: list_tables
# ---------------------------------------------------------------------------

_LIST_TABLES_SQL = """
SELECT
    c.relname AS table_name,
    GREATEST(c.reltuples, 0)::bigint AS estimated_row_count
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r'
  AND n.nspname = 'public'
ORDER BY c.relname;
"""


def list_tables(settings: Optional[Settings] = None) -> list[dict[str, Any]]:
    """Return every base table in the public schema with an estimated row
    count (from planner statistics — cheap, but not an exact COUNT(*))."""
    settings = settings or SETTINGS
    with get_connection(settings) as conn, conn.cursor() as cur:
        cur.execute(_LIST_TABLES_SQL)
        rows = cur.fetchall()
    return [
        {
            "table_name": r["table_name"],
            "estimated_row_count": int(r["estimated_row_count"]),
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Introspection: describe_table
# ---------------------------------------------------------------------------

_COLUMNS_SQL = """
SELECT column_name, data_type, is_nullable, column_default,
       character_maximum_length, numeric_precision, numeric_scale
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = %(table_name)s
ORDER BY ordinal_position;
"""

_PK_SQL = """
SELECT kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
WHERE tc.table_schema = 'public' AND tc.table_name = %(table_name)s
  AND tc.constraint_type = 'PRIMARY KEY'
ORDER BY kcu.ordinal_position;
"""

_OUTGOING_FK_SQL = """
SELECT kcu.column_name AS column_name,
       ccu.table_name AS foreign_table_name,
       ccu.column_name AS foreign_column_name,
       tc.constraint_name AS constraint_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage ccu
  ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = 'public' AND tc.table_name = %(table_name)s
ORDER BY tc.constraint_name;
"""

_INCOMING_FK_SQL = """
SELECT tc.table_name AS referencing_table,
       kcu.column_name AS referencing_column,
       ccu.column_name AS referenced_column,
       tc.constraint_name AS constraint_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage ccu
  ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND ccu.table_schema = 'public' AND ccu.table_name = %(table_name)s
ORDER BY tc.constraint_name;
"""

_CHECK_SQL = """
SELECT tc.constraint_name, cc.check_clause
FROM information_schema.table_constraints tc
JOIN information_schema.check_constraints cc
  ON tc.constraint_name = cc.constraint_name AND tc.table_schema = cc.constraint_schema
WHERE tc.table_schema = 'public' AND tc.table_name = %(table_name)s
  AND tc.constraint_type = 'CHECK'
ORDER BY tc.constraint_name;
"""


def describe_table(
    table_name: str, settings: Optional[Settings] = None
) -> dict[str, Any]:
    """Describe one table: columns, primary key, foreign keys (both
    directions), CHECK constraints, and up to 3 sample rows.

    `table_name` is checked against the live table list before being used
    to build the (otherwise unparameterizable) sample-row query, so this is
    safe against SQL injection even though it ends up as an identifier.
    """
    settings = settings or SETTINGS
    with get_connection(settings) as conn, conn.cursor() as cur:
        cur.execute(_LIST_TABLES_SQL)
        valid_tables = {r["table_name"] for r in cur.fetchall()}
        if table_name not in valid_tables:
            raise QueryValidationError(
                f"Unknown table '{table_name}'. Call list_tables() to see "
                "available tables."
            )

        cur.execute(_COLUMNS_SQL, {"table_name": table_name})
        columns = cur.fetchall()

        cur.execute(_PK_SQL, {"table_name": table_name})
        primary_key = [r["column_name"] for r in cur.fetchall()]

        cur.execute(_OUTGOING_FK_SQL, {"table_name": table_name})
        outgoing_fks = cur.fetchall()

        cur.execute(_INCOMING_FK_SQL, {"table_name": table_name})
        incoming_fks = cur.fetchall()

        cur.execute(_CHECK_SQL, {"table_name": table_name})
        checks = cur.fetchall()

        sample_query = psycopg.sql.SQL("SELECT * FROM {} LIMIT 3").format(
            psycopg.sql.Identifier(table_name)
        )
        cur.execute(sample_query)
        sample_rows = [_json_safe_row(r) for r in cur.fetchall()]

    return {
        "table_name": table_name,
        "columns": [
            {
                "name": c["column_name"],
                "type": c["data_type"],
                "nullable": c["is_nullable"] == "YES",
                "default": c["column_default"],
                "is_primary_key": c["column_name"] in primary_key,
            }
            for c in columns
        ],
        "primary_key": primary_key,
        "foreign_keys": [
            {
                "column": fk["column_name"],
                "references_table": fk["foreign_table_name"],
                "references_column": fk["foreign_column_name"],
            }
            for fk in outgoing_fks
        ],
        "referenced_by": [
            {
                "table": fk["referencing_table"],
                "column": fk["referencing_column"],
                "via_this_column": fk["referenced_column"],
            }
            for fk in incoming_fks
        ],
        "check_constraints": [c["check_clause"] for c in checks],
        "sample_rows": sample_rows,
    }


# ---------------------------------------------------------------------------
# get_schema — compact DDL-ish text dump of the whole database
# ---------------------------------------------------------------------------

_ALL_COLUMNS_SQL = """
SELECT table_name, column_name, data_type, is_nullable, character_maximum_length
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;
"""

_ALL_PK_SQL = """
SELECT tc.table_name, kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
WHERE tc.table_schema = 'public' AND tc.constraint_type = 'PRIMARY KEY'
ORDER BY tc.table_name, kcu.ordinal_position;
"""

_ALL_FK_SQL = """
SELECT tc.table_name, kcu.column_name,
       ccu.table_name AS foreign_table_name, ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage ccu
  ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
ORDER BY tc.table_name, kcu.column_name;
"""


def get_schema(settings: Optional[Settings] = None) -> str:
    """Return the whole public-schema database as one compact DDL-ish text
    blob: every table, its columns/types/nullability, primary key, and
    foreign keys. This is intentionally "dump everything into context" —
    it is the naive baseline against which a curated retrieval pipeline is
    compared, so it should NOT do any retrieval/selection of its own.
    """
    settings = settings or SETTINGS
    with get_connection(settings) as conn, conn.cursor() as cur:
        cur.execute(_ALL_COLUMNS_SQL)
        all_columns = cur.fetchall()
        cur.execute(_ALL_PK_SQL)
        all_pks = cur.fetchall()
        cur.execute(_ALL_FK_SQL)
        all_fks = cur.fetchall()

    pk_by_table: dict[str, set[str]] = {}
    for r in all_pks:
        pk_by_table.setdefault(r["table_name"], set()).add(r["column_name"])

    fk_by_table: dict[str, dict[str, tuple[str, str]]] = {}
    for r in all_fks:
        fk_by_table.setdefault(r["table_name"], {})[r["column_name"]] = (
            r["foreign_table_name"],
            r["foreign_column_name"],
        )

    columns_by_table: dict[str, list[dict[str, Any]]] = {}
    for r in all_columns:
        columns_by_table.setdefault(r["table_name"], []).append(r)

    lines: list[str] = ["-- car_rental (PostgreSQL) — auto-generated schema dump", ""]
    for table_name in sorted(columns_by_table):
        lines.append(f"TABLE {table_name}")
        pks = pk_by_table.get(table_name, set())
        fks = fk_by_table.get(table_name, {})
        for col in columns_by_table[table_name]:
            name = col["column_name"]
            dtype = col["data_type"]
            if col["character_maximum_length"]:
                dtype = f"{dtype}({col['character_maximum_length']})"
            flags = []
            if name in pks:
                flags.append("PK")
            if name in fks:
                ref_table, ref_col = fks[name]
                flags.append(f"FK -> {ref_table}.{ref_col}")
            if col["is_nullable"] == "NO" and name not in pks:
                flags.append("NOT NULL")
            flag_str = f"  [{', '.join(flags)}]" if flags else ""
            lines.append(f"  {name:<20} {dtype:<20}{flag_str}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# run_query — validated, read-only, capped execution
# ---------------------------------------------------------------------------

_ALLOWED_ROOT_TYPES = (exp.Select, exp.Union, exp.Intersect, exp.Except)

_FORBIDDEN_NODE_TYPES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.TruncateTable,
    exp.Command,
    exp.Copy,
    exp.Merge,
    exp.Grant,
    exp.Revoke,
    exp.Set,
    exp.Use,
    exp.Pragma,
)


def validate_readonly_sql(sql: str, dialect: str = "postgres") -> exp.Expression:
    """Parse `sql` with sqlglot and enforce: exactly one statement, and that
    statement is a pure SELECT (optionally with a WITH prefix, optionally
    combined via UNION/INTERSECT/EXCEPT) — no data-modifying CTEs, no
    SELECT INTO, no locking reads (FOR UPDATE/FOR SHARE).

    Raises QueryValidationError and never touches the database.
    """
    if not sql or not sql.strip():
        raise QueryValidationError("Empty query.")

    try:
        parsed = sqlglot.parse(sql, dialect=dialect)
    except Exception as e:  # sqlglot.errors.ParseError and friends
        raise QueryValidationError(f"Could not parse SQL: {e}") from e

    statements = [s for s in parsed if s is not None]
    if len(statements) == 0:
        raise QueryValidationError("Empty query.")
    if len(statements) > 1:
        raise QueryValidationError(
            f"Only a single SQL statement is allowed, found {len(statements)}."
        )

    stmt = statements[0]

    if not isinstance(stmt, _ALLOWED_ROOT_TYPES):
        raise QueryValidationError(
            f"Only SELECT statements are allowed (got {type(stmt).__name__})."
        )
    if stmt.find(exp.Select) is None:
        raise QueryValidationError("Query does not contain a SELECT.")

    for node in stmt.walk():
        if isinstance(node, _FORBIDDEN_NODE_TYPES):
            raise QueryValidationError(
                f"Disallowed SQL construct: {type(node).__name__}."
            )

    for sel in stmt.find_all(exp.Select):
        if sel.args.get("into"):
            raise QueryValidationError("SELECT INTO is not allowed.")
        if sel.args.get("locks"):
            raise QueryValidationError(
                "Locking reads (FOR UPDATE / FOR SHARE) are not allowed."
            )

    return stmt


def run_query(sql: str, settings: Optional[Settings] = None) -> dict[str, Any]:
    """Validate and execute a single read-only SQL statement.

    Returns {"columns", "rows", "row_count", "truncated", "duration_ms"}.
    Raises QueryValidationError (bad/unsafe SQL) or QueryExecutionError
    (valid SQL that Postgres rejected or timed out on).
    """
    settings = settings or SETTINGS
    validate_readonly_sql(sql, dialect=settings.sql_dialect)

    start = time.perf_counter()
    try:
        with get_connection(settings) as conn:
            with conn.cursor(row_factory=psycopg.rows.tuple_row) as cur:
                cur.execute(sql)
                col_names = (
                    [d.name for d in cur.description] if cur.description else []
                )
                fetched = cur.fetchmany(settings.max_rows + 1)
                truncated = len(fetched) > settings.max_rows
                rows = fetched[: settings.max_rows]
    except psycopg.errors.QueryCanceled as e:
        raise QueryExecutionError(
            f"Query exceeded the {settings.statement_timeout_ms}ms statement "
            "timeout and was cancelled."
        ) from e
    except psycopg.Error as e:
        raise QueryExecutionError(str(e).strip()) from e

    duration_ms = (time.perf_counter() - start) * 1000
    return {
        "columns": col_names,
        "rows": [[_json_safe_value(v) for v in row] for row in rows],
        "row_count": len(rows),
        "truncated": truncated,
        "duration_ms": round(duration_ms, 2),
    }
