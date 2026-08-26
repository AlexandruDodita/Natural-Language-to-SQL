import os
import secrets
import time

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from starlette.responses import JSONResponse

import audit
import config
import guards
import oracle_conn
import shaping

READ_ONLY_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


class BearerTokenMiddleware:
    """Pure-ASGI middleware requiring `Authorization: Bearer <token>` on every request."""

    def __init__(self, app, token: str):
        self.app = app
        self.expected = f"Bearer {token}"

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        headers = dict(scope.get("headers") or [])
        auth_header = headers.get(b"authorization", b"").decode("latin-1")

        if not secrets.compare_digest(auth_header, self.expected):
            response = JSONResponse({"error": "unauthorized"}, status_code=401)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


class AuthenticatedFastMCP(FastMCP):
    def streamable_http_app(self):
        app = super().streamable_http_app()
        return BearerTokenMiddleware(app, config.MCP_AUTH_TOKEN)


mcp = AuthenticatedFastMCP(config.MCP_SERVER_NAME, host=config.MCP_HOST, port=config.MCP_PORT)

_SCHEMA = config.ORACLE_TARGET_SCHEMA
_SEARCH_RESULTS_LIMIT = 200


def _rows_to_dicts(cursor, rows) -> list[dict]:
    return shaping.rows_to_dicts(cursor.description, rows, config.MAX_CELL_CHARS)


def _escape_like(keyword: str) -> str:
    """Escape LIKE wildcards so a keyword matches literally (paired with ESCAPE '\\')."""
    return keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _log(tool: str, detail: str, start: float, max_rows: int | None = None,
         row_count: int | None = None, outcome: str = "ok") -> None:
    duration_ms = (time.perf_counter() - start) * 1000
    audit.log_query(tool, detail, max_rows, row_count, duration_ms, outcome)


def _failure_outcome(exc: Exception) -> str:
    if isinstance(exc, (guards.QueryRejected, ValueError)):
        return f"rejected:{exc}"
    return f"error:{type(exc).__name__}"


def _require_allowed_table(table_name: str) -> str:
    if not table_name or not table_name.strip():
        raise ValueError("table_name must not be empty.")
    if not guards.is_table_allowed(table_name):
        raise ValueError(f"Table is not accessible: {table_name}")
    return table_name.strip()


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def list_tables(keyword: str | None = None) -> list[dict]:
    """
    List tables in the target schema, optionally filtered by a substring of the
    table name (case-insensitive). Returns table name and table-level comment.
    Start here when exploring an unfamiliar database.
    """
    start = time.perf_counter()
    query = """
        SELECT t.table_name, c.comments
        FROM ALL_TABLES t
        LEFT JOIN ALL_TAB_COMMENTS c
            ON c.owner = t.owner AND c.table_name = t.table_name
        WHERE t.owner = :owner
          AND (:keyword IS NULL
               OR UPPER(t.table_name) LIKE '%' || UPPER(:keyword) || '%' ESCAPE '\\')
        ORDER BY t.table_name
    """
    escaped = _escape_like(keyword) if keyword else None
    try:
        with oracle_conn.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, owner=_SCHEMA, keyword=escaped)
                rows = _rows_to_dicts(cursor, cursor.fetchall())
    except Exception as exc:
        _log("list_tables", keyword or "", start, outcome=_failure_outcome(exc))
        raise

    allowed = [row for row in rows if guards.is_table_allowed(row["TABLE_NAME"])]
    _log("list_tables", keyword or "", start, row_count=len(allowed))
    return allowed


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def describe_table(table_name: str) -> dict:
    """
    Describe a table's columns (name, type, nullability, comment), its primary key,
    and its foreign keys with the referenced table and column resolved. Call this
    before writing a run_query() against a table you have not queried before.
    """
    start = time.perf_counter()
    try:
        table_name = _require_allowed_table(table_name)

        with oracle_conn.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT comments FROM ALL_TAB_COMMENTS
                    WHERE owner = :owner AND table_name = UPPER(:tn)
                    """,
                    owner=_SCHEMA,
                    tn=table_name,
                )
                comment_row = cursor.fetchone()
                table_comment = comment_row[0] if comment_row else None

                cursor.execute(
                    """
                    SELECT col.column_name, col.data_type, col.data_length, col.data_precision,
                           col.data_scale, col.nullable, col.column_id, cmt.comments
                    FROM ALL_TAB_COLUMNS col
                    LEFT JOIN ALL_COL_COMMENTS cmt
                        ON cmt.owner = col.owner
                        AND cmt.table_name = col.table_name
                        AND cmt.column_name = col.column_name
                    WHERE col.owner = :owner AND col.table_name = UPPER(:tn)
                    ORDER BY col.column_id
                    """,
                    owner=_SCHEMA,
                    tn=table_name,
                )
                columns = _rows_to_dicts(cursor, cursor.fetchall())

                cursor.execute(
                    """
                    SELECT cons.constraint_name, cons.constraint_type, cols.column_name,
                           cols.position,
                           r_cons.table_name AS referenced_table,
                           r_cols.column_name AS referenced_column
                    FROM ALL_CONSTRAINTS cons
                    JOIN ALL_CONS_COLUMNS cols
                        ON cols.owner = cons.owner
                        AND cols.constraint_name = cons.constraint_name
                        AND cols.table_name = cons.table_name
                    LEFT JOIN ALL_CONSTRAINTS r_cons
                        ON r_cons.owner = cons.r_owner
                        AND r_cons.constraint_name = cons.r_constraint_name
                    LEFT JOIN ALL_CONS_COLUMNS r_cols
                        ON r_cols.owner = r_cons.owner
                        AND r_cols.constraint_name = r_cons.constraint_name
                        AND r_cols.position = cols.position
                    WHERE cons.owner = :owner AND cons.table_name = UPPER(:tn)
                        AND cons.constraint_type IN ('P', 'R')
                    ORDER BY cons.constraint_type, cons.constraint_name, cols.position
                    """,
                    owner=_SCHEMA,
                    tn=table_name,
                )
                constraints = _rows_to_dicts(cursor, cursor.fetchall())
    except Exception as exc:
        _log("describe_table", table_name, start, outcome=_failure_outcome(exc))
        raise

    primary_key = [c["COLUMN_NAME"] for c in constraints if c["CONSTRAINT_TYPE"] == "P"]
    foreign_keys = [
        c for c in constraints
        if c["CONSTRAINT_TYPE"] == "R"
        and (c["REFERENCED_TABLE"] is None or guards.is_table_allowed(c["REFERENCED_TABLE"]))
    ]

    _log("describe_table", table_name, start, row_count=len(columns))
    return {
        "table_name": table_name.upper(),
        "comment": table_comment,
        "columns": columns,
        "primary_key": primary_key,
        "foreign_keys": foreign_keys,
    }


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def search_columns(keyword: str) -> list[dict]:
    """
    Find columns whose name or comment matches a keyword (case-insensitive
    substring) across all accessible tables. The fastest way to locate which
    table holds a concept (e.g. 'invoice', 'status') on an unfamiliar schema;
    follow up with describe_table() on the hits.
    """
    start = time.perf_counter()
    if not keyword or not keyword.strip():
        raise ValueError("keyword must not be empty.")

    query = """
        SELECT col.table_name, col.column_name, col.data_type, cmt.comments
        FROM ALL_TAB_COLUMNS col
        LEFT JOIN ALL_COL_COMMENTS cmt
            ON cmt.owner = col.owner
            AND cmt.table_name = col.table_name
            AND cmt.column_name = col.column_name
        WHERE col.owner = :owner
          AND (UPPER(col.column_name) LIKE '%' || UPPER(:kw) || '%' ESCAPE '\\'
               OR UPPER(cmt.comments) LIKE '%' || UPPER(:kw) || '%' ESCAPE '\\')
        ORDER BY col.table_name, col.column_id
    """
    try:
        with oracle_conn.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, owner=_SCHEMA, kw=_escape_like(keyword.strip()))
                rows = _rows_to_dicts(cursor, cursor.fetchall())
    except Exception as exc:
        _log("search_columns", keyword, start, outcome=_failure_outcome(exc))
        raise

    allowed = [row for row in rows if guards.is_table_allowed(row["TABLE_NAME"])]
    allowed = allowed[:_SEARCH_RESULTS_LIMIT]
    _log("search_columns", keyword, start, row_count=len(allowed))
    return allowed


_LOB_TYPES = {"CLOB", "NCLOB", "BLOB", "LONG", "LONG RAW", "BFILE"}
_TOP_VALUES_LIMIT = 15
_TOP_VALUES_DISTINCT_THRESHOLD = 100


def _require_allowed_column(table_name: str, column_name: str) -> tuple[str, str, str]:
    """Validate table_name/column_name and return their canonical dictionary values.

    table_name/column_name end up spliced into a dynamically built SQL string
    below (Oracle cannot bind identifiers, only values), which is exactly the
    injection surface describe_table()/list_related_tables() avoid by only ever
    comparing names as bound literals against dictionary views. The guard here
    is the same idea one step later: never use the caller's raw string as an
    identifier, only the value the dictionary itself returned for an existing
    column on an allowed table.
    """
    table_name = _require_allowed_table(table_name)
    if not column_name or not column_name.strip():
        raise ValueError("column_name must not be empty.")

    with oracle_conn.get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name, data_type
                FROM ALL_TAB_COLUMNS
                WHERE owner = :owner AND table_name = UPPER(:tn) AND column_name = UPPER(:cn)
                """,
                owner=_SCHEMA,
                tn=table_name,
                cn=column_name.strip(),
            )
            row = cursor.fetchone()

    if row is None:
        raise ValueError(f"Column not found on table {table_name.upper()}: {column_name}")

    return table_name.upper(), row[0], row[1]


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def column_stats(table_name: str, column_name: str) -> dict:
    """
    Summarize a column's values: row count, null count, approximate distinct
    count, min/max, and -- for low-cardinality columns only -- the most
    frequent values with their counts. Call describe_table() first to see
    what columns are available and their types.
    """
    start = time.perf_counter()
    label = f"{table_name}.{column_name}"
    try:
        table_name, column_name, data_type = _require_allowed_column(table_name, column_name)

        if data_type in _LOB_TYPES:
            raise ValueError(f"Column stats are not supported for {data_type} columns.")

        table_ident = f'"{_SCHEMA}"."{table_name}"'
        col_ident = f'"{column_name}"'
        label = f"{table_name}.{column_name}"

        summary_sql = (
            f"SELECT COUNT(*), COUNT({col_ident}), APPROX_COUNT_DISTINCT({col_ident}), "
            f"MIN({col_ident}), MAX({col_ident}) FROM {table_ident}"
        )

        with oracle_conn.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(summary_sql)
                row_count, non_null_count, distinct_count, min_value, max_value = cursor.fetchone()

                top_values = None
                if distinct_count is not None and distinct_count <= _TOP_VALUES_DISTINCT_THRESHOLD:
                    cursor.execute(
                        f"SELECT {col_ident}, COUNT(*) FROM {table_ident} "
                        f"GROUP BY {col_ident} ORDER BY COUNT(*) DESC "
                        f"FETCH FIRST {_TOP_VALUES_LIMIT} ROWS ONLY"
                    )
                    top_values = [
                        {"value": shaping.serialize_value(value, config.MAX_CELL_CHARS), "count": count}
                        for value, count in cursor.fetchall()
                    ]
    except Exception as exc:
        _log("column_stats", label, start, max_rows=_TOP_VALUES_LIMIT, outcome=_failure_outcome(exc))
        raise

    _log(
        "column_stats",
        label,
        start,
        max_rows=_TOP_VALUES_LIMIT,
        row_count=len(top_values) if top_values is not None else None,
    )

    return {
        "table_name": table_name,
        "column_name": column_name,
        "data_type": data_type,
        "row_count": row_count,
        "null_count": row_count - non_null_count,
        "distinct_count": distinct_count,
        "min_value": shaping.serialize_value(min_value, config.MAX_CELL_CHARS),
        "max_value": shaping.serialize_value(max_value, config.MAX_CELL_CHARS),
        "top_values": top_values,
    }


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def list_related_tables(table_name: str) -> list[dict]:
    """
    Discover foreign-key join paths for a table: tables it references (outgoing)
    and tables that reference it (incoming). Useful before writing multi-table
    run_query() joins on an unfamiliar schema.
    """
    start = time.perf_counter()
    outgoing_query = """
        SELECT a.column_name AS local_column, c_pk.table_name AS related_table,
               b.column_name AS related_column
        FROM all_cons_columns a
        JOIN all_constraints c
            ON c.owner = a.owner
            AND c.constraint_name = a.constraint_name
            AND c.table_name = a.table_name
        JOIN all_constraints c_pk
            ON c_pk.owner = c.r_owner AND c_pk.constraint_name = c.r_constraint_name
        JOIN all_cons_columns b
            ON b.owner = c_pk.owner
            AND b.constraint_name = c_pk.constraint_name
            AND b.position = a.position
        WHERE c.constraint_type = 'R'
          AND a.owner = :owner AND c_pk.owner = :owner
          AND a.table_name = UPPER(:tn)
    """
    incoming_query = """
        SELECT a.column_name AS related_column, c.table_name AS related_table,
               b.column_name AS local_column
        FROM all_cons_columns a
        JOIN all_constraints c
            ON c.owner = a.owner
            AND c.constraint_name = a.constraint_name
            AND c.table_name = a.table_name
        JOIN all_constraints c_pk
            ON c_pk.owner = c.r_owner AND c_pk.constraint_name = c.r_constraint_name
        JOIN all_cons_columns b
            ON b.owner = c_pk.owner
            AND b.constraint_name = c_pk.constraint_name
            AND b.position = a.position
        WHERE c.constraint_type = 'R'
          AND a.owner = :owner AND c_pk.owner = :owner
          AND c_pk.table_name = UPPER(:tn)
    """
    try:
        table_name = _require_allowed_table(table_name)

        with oracle_conn.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(outgoing_query, owner=_SCHEMA, tn=table_name)
                outgoing = _rows_to_dicts(cursor, cursor.fetchall())
                for row in outgoing:
                    row["direction"] = "outgoing"

                cursor.execute(incoming_query, owner=_SCHEMA, tn=table_name)
                incoming = _rows_to_dicts(cursor, cursor.fetchall())
                for row in incoming:
                    row["direction"] = "incoming"
    except Exception as exc:
        _log("list_related_tables", table_name, start, outcome=_failure_outcome(exc))
        raise

    related = outgoing + incoming
    allowed = [row for row in related if guards.is_table_allowed(row["RELATED_TABLE"])]
    _log("list_related_tables", table_name, start, row_count=len(allowed))
    return allowed


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def run_query(sql: str, max_rows: int = 200) -> dict:
    """
    Execute a read-only SELECT query against the target schema. Returns
    {"rows": [...], "row_count": N, "truncated": bool} -- when `truncated` is
    true more rows exist than were returned, so use COUNT(*) or aggregation
    instead of paging blindly.

    Rules enforced automatically before anything reaches the database:
    - Exactly one SELECT statement (optionally a WITH ... SELECT); no DML, DDL,
      PL/SQL blocks, transaction control, or calls into DBMS_*/UTL_*/SYS packages.
    - No semicolons, no SQL comments (-- or /* */), no database links (@).
    - At most `max_rows` rows are returned, capped server-side regardless of the
      value requested. Oversized text cells are truncated with a marker.
    - Tables on the server's denylist are not queryable.

    Call describe_table() first if you are not already familiar with a table's
    columns, and list_related_tables() to discover join paths.
    """
    start = time.perf_counter()

    try:
        validated_sql = guards.validate_query(sql)
    except guards.QueryRejected as exc:
        _log("run_query", sql, start, max_rows=max_rows, outcome=f"rejected:{exc}")
        raise

    capped = guards.clamp_row_limit(max_rows)

    try:
        with oracle_conn.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(validated_sql)
                # One row past the cap distinguishes "exactly `capped` rows
                # exist" from "results were cut off".
                raw_rows = cursor.fetchmany(capped + 1)
                truncated = len(raw_rows) > capped
                rows = _rows_to_dicts(cursor, raw_rows[:capped])
    except Exception as exc:
        _log("run_query", validated_sql, start, max_rows=capped, outcome=f"error:{type(exc).__name__}")
        raise

    rows, dropped = shaping.cap_payload(rows, config.MAX_RESPONSE_CHARS)
    truncated = truncated or dropped > 0

    result = {"rows": rows, "row_count": len(rows), "truncated": truncated}
    if dropped:
        result["note"] = (
            f"Dropped {dropped} trailing rows to fit the response size cap; "
            "select fewer columns or aggregate instead."
        )

    _log("run_query", validated_sql, start, max_rows=capped, row_count=len(rows))
    return result


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "streamable-http")
    mcp.run(transport=transport)
