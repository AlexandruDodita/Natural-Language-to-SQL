"""
server.py — the PostgreSQL MCP server (stdio transport).

This is the thesis's "naive MCP" baseline: it exposes the schema and a
query tool and lets the model figure out the rest, with no retrieval
curation or self-repair logic of its own (that's what the custom
rag-service pipeline does, and what this baseline is measured against).

All actual DB logic lives in db.py, which has no MCP dependency — this
module is a thin tool-registration layer on top of it.

Run standalone:
    python server.py

Register with an MCP client (Claude Desktop / Claude Code) by pointing it
at this file with `python` as the command — see README.md for the exact
config snippet.
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("postgres-mcp")

mcp = FastMCP(
    name="postgres",
    instructions=(
        "Read-only access to the car_rental PostgreSQL database. "
        "Call list_tables() or get_schema() first to see what's available, "
        "then describe_table(name) if you need more detail on one table "
        "(sample rows, constraints, FK relationships), then run_query(sql) "
        "with a single SELECT statement to answer the question. "
        "Only SELECT (optionally WITH ... SELECT) statements are permitted; "
        "results are capped and the connection is strictly read-only."
    ),
)


@mcp.tool()
def list_tables() -> list[dict]:
    """List every table in the database's public schema, with an estimated
    row count (from Postgres planner statistics, not an exact COUNT(*)).
    Call this first to see what's available before writing SQL."""
    return db.list_tables()


@mcp.tool()
def describe_table(table_name: str) -> dict:
    """Describe one table in detail: every column's name/type/nullability,
    its primary key, its foreign key relationships (both the tables it
    references and the tables that reference it), CHECK constraints, and up
    to 3 sample rows. Use the exact table name returned by list_tables()."""
    try:
        return db.describe_table(table_name)
    except db.QueryValidationError as e:
        return {"error": str(e)}


@mcp.tool()
def get_schema() -> str:
    """Return the entire database schema — every table, its columns/types,
    primary keys, and foreign keys — as one compact text blob, so you don't
    need to call describe_table() for every table individually."""
    return db.get_schema()


@mcp.tool()
def run_query(sql: str) -> dict:
    """Execute a single read-only SQL statement (SELECT, or WITH ... SELECT)
    against the database and return its results.

    Exactly one statement is allowed and it must not modify data — no
    INSERT/UPDATE/DELETE/DDL, no SELECT INTO, no locking reads, no
    data-modifying CTEs. Rows are capped at the server's configured MAX_ROWS
    and the query is aborted if it exceeds the configured statement
    timeout. Returns {columns, rows, row_count, truncated, duration_ms} on
    success, or {error} if the SQL was rejected or failed to execute."""
    try:
        return db.run_query(sql)
    except (db.QueryValidationError, db.QueryExecutionError) as e:
        return {"error": str(e)}


if __name__ == "__main__":
    logger.info(
        "Starting postgres MCP server (db=%s, max_rows=%d, statement_timeout_ms=%d)",
        db.SETTINGS.database_url.split("@")[-1],  # don't log credentials
        db.SETTINGS.max_rows,
        db.SETTINGS.statement_timeout_ms,
    )
    mcp.run(transport="stdio")
