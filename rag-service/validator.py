"""AST-based SQL validation (replaces the keyword blocklist).

The old validator scanned tokens for forbidden words, which both over-blocks
(a column called ``update_date``) and under-blocks (anything the tokenizer does
not label as a keyword). Here the statement is parsed with ``sqlglot`` and the
resulting tree must match an allowlist shape:

* exactly one statement, and it must be a query (SELECT / WITH / set operation);
* no DDL/DML node anywhere in the tree, and nothing that sqlglot could only
  parse as an opaque ``Command`` (``COPY``, ``SET``, ``VACUUM``, ...);
* no system catalog access (``pg_*`` / ``information_schema``);
* no dangerous function (file access, sleep, dblink, configuration changes);
* every referenced table must exist in the introspected catalog;
* a ``LIMIT`` is injected or clamped so a query cannot exhaust the server.

The dialect is a parameter (``postgres`` today, ``oracle`` later).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable, Optional

import sqlglot
from sqlglot import exp

logger = logging.getLogger(__name__)

# Node types that must never appear anywhere in the tree.
FORBIDDEN_NODES: tuple[type, ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.Merge,
    exp.Grant,
    exp.Command,  # anything sqlglot could not parse as a query
    exp.Into,     # SELECT ... INTO
    exp.Lock,     # SELECT ... FOR UPDATE
    exp.Placeholder,
    exp.Parameter,
)

QUERY_NODES: tuple[type, ...] = (exp.Select, exp.Subquery, exp.SetOperation)

BLOCKED_SCHEMAS = {"pg_catalog", "information_schema", "pg_toast", "pg_temp"}

BLOCKED_FUNCTION_PREFIXES = ("pg_", "lo_", "dblink", "pgp_")

BLOCKED_FUNCTIONS = {
    "set_config",
    "current_setting",
    "query_to_xml",
    "query_to_xmlschema",
    "xmlelement",
    "system",
    "shell",
    "utl_file",
    "utl_http",
    "dbms_lock",
}


@dataclass
class ValidationResult:
    ok: bool
    sql: str = ""
    error: Optional[str] = None
    tables: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    limit_applied: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "error": self.error,
            "tables": self.tables,
            "limit_applied": self.limit_applied,
        }


class SqlValidator:
    def __init__(
        self,
        dialect: str = "postgres",
        max_rows: int = 200,
        known_tables: Optional[Iterable[str]] = None,
        enforce_known_tables: bool = True,
    ):
        self.dialect = dialect
        self.max_rows = max_rows
        self.known_tables = {t.lower().split(".")[-1] for t in (known_tables or [])}
        self.enforce_known_tables = enforce_known_tables

    # -- public API -------------------------------------------------------
    def validate(self, sql: str) -> ValidationResult:
        raw = (sql or "").strip().rstrip(";").strip()
        if not raw:
            return ValidationResult(False, error="Empty query.")

        try:
            statements = [s for s in sqlglot.parse(raw, dialect=self.dialect) if s]
        except Exception as exc:
            return ValidationResult(False, error=f"SQL parse error: {exc}")

        if len(statements) == 0:
            return ValidationResult(False, error="Empty query.")
        if len(statements) > 1:
            return ValidationResult(
                False, error="Multiple statements are not allowed."
            )

        tree = statements[0]

        if not isinstance(tree, QUERY_NODES + (exp.With,)):
            return ValidationResult(
                False,
                error=f"Only SELECT queries are allowed (got {type(tree).__name__.upper()}).",
            )

        for node in tree.walk():
            for forbidden in FORBIDDEN_NODES:
                if isinstance(node, forbidden):
                    return ValidationResult(
                        False,
                        error=f"Forbidden SQL construct: {type(node).__name__.upper()}.",
                    )

        cte_names = {
            cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)
        }

        tables: list[str] = []
        for table in tree.find_all(exp.Table):
            schema = (table.db or "").lower()
            name = table.name.lower()
            if schema in BLOCKED_SCHEMAS or name.startswith("pg_"):
                return ValidationResult(
                    False,
                    error=f"Access to system catalog '{table.sql(dialect=self.dialect)}' is not allowed.",
                )
            if name in cte_names:
                continue
            qualified = f"{schema}.{name}" if schema and schema != "public" else name
            if qualified not in tables:
                tables.append(qualified)

        functions: list[str] = []
        for func in tree.find_all(exp.Anonymous):
            fname = str(func.this).lower()
            functions.append(fname)
            if fname in BLOCKED_FUNCTIONS or fname.startswith(
                BLOCKED_FUNCTION_PREFIXES
            ):
                return ValidationResult(
                    False, error=f"Function '{fname}' is not allowed."
                )

        if self.enforce_known_tables and self.known_tables:
            unknown = [t for t in tables if t.split(".")[-1] not in self.known_tables]
            if unknown:
                return ValidationResult(
                    False,
                    error=(
                        f"Unknown table(s): {', '.join(unknown)}. "
                        f"Available tables: {', '.join(sorted(self.known_tables))}."
                    ),
                )

        tree, limit_applied = self.enforce_limit(tree)

        return ValidationResult(
            ok=True,
            sql=tree.sql(dialect=self.dialect, pretty=False),
            tables=tables,
            functions=functions,
            limit_applied=limit_applied,
        )

    # -- helpers ----------------------------------------------------------
    def enforce_limit(self, tree: exp.Expression) -> tuple[exp.Expression, Optional[int]]:
        """Ensure the top-level query carries a LIMIT of at most ``max_rows``."""
        limit = tree.args.get("limit") if hasattr(tree, "args") else None
        current: Optional[int] = None
        if isinstance(limit, exp.Limit):
            try:
                current = int(limit.expression.name)
            except (AttributeError, ValueError, TypeError):
                current = None

        if current is not None and current <= self.max_rows:
            return tree, current

        try:
            return tree.limit(self.max_rows), self.max_rows
        except Exception:
            wrapped = sqlglot.parse_one(
                f"SELECT * FROM ({tree.sql(dialect=self.dialect)}) AS _capped "
                f"LIMIT {self.max_rows}",
                dialect=self.dialect,
            )
            return wrapped, self.max_rows
