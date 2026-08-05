"""SQL execution back-ends.

Two runners implement the same interface:

* ``HttpRunner``   -- posts to the Rust service (``POST /api/sql``), which uses
  the ``readonly_user`` pool. This is the historical path and stays the default
  so nothing in the existing deployment changes.
* ``DirectRunner`` -- talks to PostgreSQL with psycopg. Needed for schema
  introspection, for ``EXPLAIN`` dry-runs, and for the row-level-security demo
  (``SET LOCAL ROLE`` + ``SET LOCAL app.location_id``), none of which can go
  through the Rust endpoint because it only accepts statements starting with
  ``SELECT``.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

import httpx

logger = logging.getLogger(__name__)


class SqlExecutionError(RuntimeError):
    """Raised when the database (or the SQL backend) rejects a query.

    The message is fed verbatim back to the model by the repair loop, so it must
    stay close to the original database error text.
    """


@dataclass
class QueryResult:
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    row_count: int = 0
    duration_ms: float = 0.0
    truncated: bool = False

    def to_dict(self) -> dict:
        return {
            "columns": self.columns,
            "rows": self.rows,
            "row_count": self.row_count,
            "duration_ms": self.duration_ms,
            "truncated": self.truncated,
        }


@dataclass
class SessionContext:
    """Database session attributes used by the RLS layer."""

    role: Optional[str] = None
    location_id: Optional[int] = None
    user_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Pure helpers (no connection needed -> unit-testable)
# ---------------------------------------------------------------------------
def parse_sql_response(payload: dict) -> QueryResult:
    """Shape the Rust service's JSON body into a QueryResult."""
    return QueryResult(
        columns=list(payload.get("columns") or []),
        rows=[list(r) for r in (payload.get("rows") or [])],
        row_count=int(payload.get("row_count") or 0),
        duration_ms=float(payload.get("duration_ms") or 0.0),
    )


def extract_http_error(status_code: int, body_text: str, body_json: Any = None) -> str:
    """Pick the most useful error text out of an HTTP error response."""
    if isinstance(body_json, dict):
        for key in ("error", "detail", "message"):
            value = body_json.get(key)
            if value:
                return str(value)
    text = (body_text or "").strip()
    return text or f"SQL backend returned HTTP {status_code}"


def session_statements(
    session: Optional[SessionContext], statement_timeout_ms: int
) -> list[tuple[str, Optional[tuple]]]:
    """The SET LOCAL statements applied before a query.

    Role names come from the policy file (never from user input) and are quoted
    as identifiers; the context values are passed as bound parameters.
    """
    stmts: list[tuple[str, Optional[tuple]]] = [
        (f"SET LOCAL statement_timeout = {int(statement_timeout_ms)}", None),
        ("SET LOCAL transaction_read_only = on", None),
    ]
    if session is None:
        return stmts
    if session.location_id is not None:
        stmts.append(
            (
                "SELECT set_config('app.location_id', %s, true)",
                (str(session.location_id),),
            )
        )
    if session.user_id:
        stmts.append(
            ("SELECT set_config('app.user_id', %s, true)", (str(session.user_id),))
        )
    if session.role:
        safe_role = str(session.role).replace('"', "")
        stmts.append((f'SET LOCAL ROLE "{safe_role}"', None))
    return stmts


class HttpRunner:
    """Executes SELECTs through the Rust SQL service."""

    name = "http"
    supports_explain = False
    supports_session_context = False

    def __init__(self, base_url: str, timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def execute(
        self, sql: str, session: Optional[SessionContext] = None
    ) -> QueryResult:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/api/sql", json={"query": sql}
                )
        except httpx.HTTPError as exc:  # network level
            raise SqlExecutionError(f"SQL backend unreachable: {exc}") from exc

        if resp.status_code >= 400:
            try:
                body_json = resp.json()
            except Exception:  # pragma: no cover - non JSON error body
                body_json = None
            raise SqlExecutionError(
                extract_http_error(resp.status_code, resp.text, body_json)
            )

        return parse_sql_response(resp.json())

    async def explain(self, sql: str, session: Optional[SessionContext] = None) -> None:
        raise NotImplementedError("HTTP runner cannot run EXPLAIN")


class DirectRunner:
    """Executes SQL against PostgreSQL through psycopg (async)."""

    name = "direct"
    supports_explain = True
    supports_session_context = True

    def __init__(self, dsn: str, statement_timeout_ms: int = 5000):
        self.dsn = dsn
        self.statement_timeout_ms = statement_timeout_ms

    # -- internals --------------------------------------------------------
    async def _connect(self):
        import psycopg  # imported lazily so the service starts without psycopg

        return await psycopg.AsyncConnection.connect(self.dsn, autocommit=False)

    async def _prepare_session(self, cur, session: Optional[SessionContext]) -> None:
        for sql, params in session_statements(session, self.statement_timeout_ms):
            await cur.execute(sql, params)

    # -- public API -------------------------------------------------------
    async def execute(
        self,
        sql: str,
        session: Optional[SessionContext] = None,
        params: Optional[Sequence[Any]] = None,
    ) -> QueryResult:
        import psycopg

        start = time.perf_counter()
        try:
            conn = await self._connect()
        except Exception as exc:
            raise SqlExecutionError(f"cannot connect to database: {exc}") from exc
        try:
            async with conn.cursor() as cur:
                await self._prepare_session(cur, session)
                await cur.execute(sql, params)
                columns = [d.name for d in (cur.description or [])]
                rows = await cur.fetchall() if cur.description else []
            await conn.rollback()
        except psycopg.Error as exc:
            await conn.rollback()
            raise SqlExecutionError(_pg_error_text(exc)) from exc
        finally:
            await conn.close()

        duration_ms = (time.perf_counter() - start) * 1000.0
        json_rows = [[to_jsonable(v) for v in row] for row in rows]
        return QueryResult(
            columns=columns,
            rows=json_rows,
            row_count=len(json_rows),
            duration_ms=duration_ms,
        )

    async def explain(self, sql: str, session: Optional[SessionContext] = None) -> None:
        """Plan the query without running it. Raises SqlExecutionError if invalid."""
        await self.execute(f"EXPLAIN {sql}", session=session)


def _pg_error_text(exc: Exception) -> str:
    parts = [str(exc).strip()]
    diag = getattr(exc, "diag", None)
    hint = getattr(diag, "message_hint", None) if diag else None
    if hint:
        parts.append(f"HINT: {hint}")
    return " ".join(p for p in parts if p)


def to_jsonable(value: Any) -> Any:
    import datetime
    import decimal
    import uuid

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, datetime.datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, (datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    return str(value)


def build_runners(settings) -> tuple[Any, Optional[DirectRunner]]:
    """Return (execution runner, direct runner or None).

    The direct runner is also used for introspection and EXPLAIN even when
    execution goes through HTTP.
    """
    direct: Optional[DirectRunner] = None
    if settings.target_database_url:
        direct = DirectRunner(
            settings.target_database_url, settings.statement_timeout_ms
        )

    if settings.executor == "direct":
        if direct is None:
            logger.warning(
                "SQL_EXECUTOR=direct but TARGET_DATABASE_URL is empty; "
                "falling back to the HTTP runner"
            )
        else:
            return direct, direct

    return HttpRunner(settings.sql_backend_url), direct
