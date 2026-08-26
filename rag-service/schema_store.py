"""Live schema introspection.

Replaces the hard-coded ``SCHEMA`` string of the original prototype. The
catalog is read from ``pg_catalog``/``information_schema`` at startup, so the
service works against *any* PostgreSQL database given a connection URL — which
is what makes the multi-database claim of the thesis true.

The catalog is cached on disk: if the database is unreachable at boot the last
known catalog is reused, and the (expensive) embedding index is keyed on the
catalog fingerprint so it is only rebuilt when the schema actually changes.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

logger = logging.getLogger(__name__)

_RELKINDS = ("r", "v", "m", "p", "f")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class ForeignKey:
    columns: list[str]
    ref_table: str
    ref_columns: list[str]


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    nullable: bool = True
    default: Optional[str] = None
    comment: Optional[str] = None
    is_primary_key: bool = False
    is_unique: bool = False
    check: Optional[str] = None
    references: Optional[str] = None  # "table.column"

    def render(self) -> str:
        bits = [f"{self.name} {self.data_type}"]
        if self.is_primary_key:
            bits.append("PK")
        if self.references:
            bits.append(f"FK->{self.references}")
        if self.is_unique and not self.is_primary_key:
            bits.append("UNIQUE")
        if not self.nullable:
            bits.append("NOT NULL")
        if self.check:
            bits.append(self.check)
        line = ", ".join(bits)
        if self.comment:
            line += f"  -- {self.comment}"
        return line


@dataclass
class TableInfo:
    schema: str
    name: str
    kind: str = "r"
    comment: Optional[str] = None
    row_estimate: int = 0
    columns: list[ColumnInfo] = field(default_factory=list)
    foreign_keys: list[ForeignKey] = field(default_factory=list)

    @property
    def qualified_name(self) -> str:
        return self.name if self.schema == "public" else f"{self.schema}.{self.name}"

    def column(self, name: str) -> Optional[ColumnInfo]:
        lowered = name.lower()
        for col in self.columns:
            if col.name.lower() == lowered:
                return col
        return None

    def render(self) -> str:
        """DDL-like rendering injected into the prompt."""
        header = f"{self.qualified_name}("
        lines = [header]
        for col in self.columns:
            lines.append(f"    {col.render()}")
        lines.append(")")
        if self.comment:
            lines.append(f"  -- {self.comment}")
        if self.row_estimate:
            lines.append(f"  -- approx. {self.row_estimate} rows")
        return "\n".join(lines)

    def description(self) -> str:
        """Free text used to embed the table for retrieval."""
        parts = [f"table {self.qualified_name}"]
        if self.comment:
            parts.append(self.comment)
        parts.append("columns: " + ", ".join(c.name for c in self.columns))
        typed = ", ".join(f"{c.name} {c.data_type}" for c in self.columns)
        parts.append(typed)
        for fk in self.foreign_keys:
            parts.append(
                f"joins {fk.ref_table} on {', '.join(fk.columns)}"
            )
        checks = [c.check for c in self.columns if c.check]
        if checks:
            parts.append(" ".join(checks))
        col_comments = [c.comment for c in self.columns if c.comment]
        if col_comments:
            parts.append(" ".join(col_comments))
        return ". ".join(parts)


@dataclass
class SchemaCatalog:
    database: str = ""
    tables: list[TableInfo] = field(default_factory=list)
    fingerprint: str = ""

    def table(self, name: str) -> Optional[TableInfo]:
        lowered = name.lower().split(".")[-1]
        for t in self.tables:
            if t.name.lower() == lowered:
                return t
        return None

    @property
    def table_names(self) -> list[str]:
        return [t.qualified_name for t in self.tables]

    def neighbours(self, table_name: str) -> list[str]:
        """Tables directly reachable through a foreign key, in both directions."""
        out: list[str] = []
        target = self.table(table_name)
        if target is None:
            return out
        for fk in target.foreign_keys:
            out.append(fk.ref_table)
        for t in self.tables:
            for fk in t.foreign_keys:
                if fk.ref_table.lower() == target.qualified_name.lower():
                    out.append(t.qualified_name)
        seen, unique = set(), []
        for name in out:
            if name.lower() not in seen and name.lower() != table_name.lower():
                seen.add(name.lower())
                unique.append(name)
        return unique

    def render(self, table_names: Optional[list[str]] = None) -> str:
        wanted = (
            [t for t in self.tables if t.qualified_name in set(table_names or [])]
            if table_names is not None
            else list(self.tables)
        )
        header = f"Database: {self.database} (PostgreSQL)\n\nTables:\n"
        return header + "\n\n".join(t.render() for t in wanted)

    def compute_fingerprint(self) -> str:
        payload = json.dumps(
            [asdict(t) for t in self.tables], sort_keys=True, default=str
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    # -- serialization ----------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "database": self.database,
            "fingerprint": self.fingerprint,
            "tables": [asdict(t) for t in self.tables],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SchemaCatalog":
        tables = []
        for t in data.get("tables", []):
            columns = [ColumnInfo(**c) for c in t.get("columns", [])]
            fks = [ForeignKey(**f) for f in t.get("foreign_keys", [])]
            tables.append(
                TableInfo(
                    schema=t["schema"],
                    name=t["name"],
                    kind=t.get("kind", "r"),
                    comment=t.get("comment"),
                    row_estimate=t.get("row_estimate", 0),
                    columns=columns,
                    foreign_keys=fks,
                )
            )
        return cls(
            database=data.get("database", ""),
            tables=tables,
            fingerprint=data.get("fingerprint", ""),
        )

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, default=str)

    @classmethod
    def load(cls, path: str) -> Optional["SchemaCatalog"]:
        try:
            with open(path, encoding="utf-8") as fh:
                return cls.from_dict(json.load(fh))
        except (OSError, json.JSONDecodeError):
            return None


# ---------------------------------------------------------------------------
# Introspection queries
# ---------------------------------------------------------------------------
TABLES_SQL = """
SELECT n.nspname                AS schema_name,
       c.relname                AS table_name,
       c.relkind::text          AS kind,
       obj_description(c.oid)   AS comment,
       GREATEST(c.reltuples, 0)::bigint AS row_estimate
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = ANY(%(kinds)s)
  AND n.nspname = ANY(%(schemas)s)
ORDER BY n.nspname, c.relname
"""

COLUMNS_SQL = """
SELECT n.nspname AS schema_name,
       c.relname AS table_name,
       a.attname AS column_name,
       format_type(a.atttypid, a.atttypmod) AS data_type,
       a.attnotnull AS not_null,
       pg_get_expr(d.adbin, d.adrelid) AS default_expr,
       col_description(c.oid, a.attnum) AS comment
FROM pg_attribute a
JOIN pg_class c ON c.oid = a.attrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_attrdef d ON d.adrelid = c.oid AND d.adnum = a.attnum
WHERE a.attnum > 0
  AND NOT a.attisdropped
  AND c.relkind = ANY(%(kinds)s)
  AND n.nspname = ANY(%(schemas)s)
ORDER BY n.nspname, c.relname, a.attnum
"""

CONSTRAINTS_SQL = """
SELECT n.nspname  AS schema_name,
       c.relname  AS table_name,
       con.contype::text AS contype,
       pg_get_constraintdef(con.oid) AS definition,
       ARRAY(SELECT a.attname FROM unnest(con.conkey) k
             JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k) AS columns,
       fn.nspname AS ref_schema,
       fc.relname AS ref_table,
       ARRAY(SELECT a.attname FROM unnest(con.confkey) k
             JOIN pg_attribute a ON a.attrelid = fc.oid AND a.attnum = k) AS ref_columns
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_class fc ON fc.oid = con.confrelid
LEFT JOIN pg_namespace fn ON fn.oid = fc.relnamespace
WHERE n.nspname = ANY(%(schemas)s)
"""

DATABASE_SQL = "SELECT current_database()"


async def introspect(runner, schemas: list[str]) -> SchemaCatalog:
    """Run the introspection queries and hand the rows to :func:`build_catalog`.

    This function is the only part of introspection that needs a connection;
    all the interpretation happens in ``build_catalog``, which is pure and
    therefore unit-testable without a database.
    """
    params = {"kinds": list(_RELKINDS), "schemas": schemas}

    db_res = await runner.execute(DATABASE_SQL)
    database = db_res.rows[0][0] if db_res.rows else ""

    tables_res = await runner.execute(TABLES_SQL, params=params)
    columns_res = await runner.execute(COLUMNS_SQL, params=params)
    cons_res = await runner.execute(CONSTRAINTS_SQL, params={"schemas": schemas})

    return build_catalog(database, tables_res.rows, columns_res.rows, cons_res.rows)


def build_catalog(
    database: str,
    table_rows: list,
    column_rows: list,
    constraint_rows: list,
) -> SchemaCatalog:
    """Pure: turn introspection rows into a :class:`SchemaCatalog`.

    Row shapes match TABLES_SQL / COLUMNS_SQL / CONSTRAINTS_SQL.
    """
    tables: dict[tuple[str, str], TableInfo] = {}
    for schema_name, table_name, kind, comment, row_estimate in table_rows:
        tables[(schema_name, table_name)] = TableInfo(
            schema=schema_name,
            name=table_name,
            kind=kind,
            comment=comment,
            row_estimate=int(row_estimate or 0),
        )

    for row in column_rows:
        schema_name, table_name, col, dtype, not_null, default, comment = row
        table = tables.get((schema_name, table_name))
        if table is None:
            continue
        table.columns.append(
            ColumnInfo(
                name=col,
                data_type=dtype,
                nullable=not bool(not_null),
                default=default,
                comment=comment,
            )
        )

    for row in constraint_rows:
        (
            schema_name,
            table_name,
            contype,
            definition,
            cols,
            ref_schema,
            ref_table,
            ref_cols,
        ) = row
        table = tables.get((schema_name, table_name))
        if table is None:
            continue
        cols = list(cols or [])
        if contype == "p":
            for name in cols:
                col = table.column(name)
                if col:
                    col.is_primary_key = True
        elif contype == "u":
            for name in cols:
                col = table.column(name)
                if col:
                    col.is_unique = True
        elif contype == "f" and ref_table:
            ref_qualified = (
                ref_table if ref_schema == "public" else f"{ref_schema}.{ref_table}"
            )
            table.foreign_keys.append(
                ForeignKey(
                    columns=cols,
                    ref_table=ref_qualified,
                    ref_columns=list(ref_cols or []),
                )
            )
            for i, name in enumerate(cols):
                col = table.column(name)
                if col:
                    target_col = (
                        list(ref_cols or [])[i] if i < len(ref_cols or []) else "id"
                    )
                    col.references = f"{ref_qualified}.{target_col}"
        elif contype == "c" and definition:
            clause = _shorten_check(definition)
            target = _check_target_column(table, definition)
            if target is not None:
                existing = target.check
                target.check = clause if not existing else f"{existing} {clause}"

    catalog = SchemaCatalog(
        database=database, tables=sorted(tables.values(), key=lambda t: t.qualified_name)
    )
    catalog.fingerprint = catalog.compute_fingerprint()
    return catalog


def _shorten_check(definition: str) -> str:
    """Turn PostgreSQL's normalised CHECK text into something prompt-friendly.

    ``CHECK ((role)::text = ANY ((ARRAY['manager'::character varying, ...])::text[]))``
    becomes ``CHECK(role IN ('manager', 'agent', ...))``.
    """
    import re

    text = definition.strip()
    if text.upper().startswith("CHECK"):
        text = text[5:].strip()
    # drop casts: ::text, ::character varying, ::double precision, ::text[]
    text = re.sub(
        r"::\s*[a-zA-Z_]+(?:\s+(?:varying|precision))?(?:\s*\[\s*\])?", " ", text
    )
    text = re.sub(r"\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)", r"\1", text)  # (role) -> role
    text = re.sub(
        r"=\s*ANY\s*\(*\s*ARRAY\s*\[([^\]]*)\]\s*\)*", r"IN (\1)", text
    )
    text = " ".join(text.split())
    text = re.sub(r"\s+([,)])", r"\1", text)
    text = _balance_parens(text)
    while text.startswith("(") and text.endswith(")") and _balance_parens(text[1:-1]) == text[1:-1]:
        text = text[1:-1].strip()
    if len(text) > 200:
        text = text[:197] + "..."
    return f"CHECK({text})"


def _balance_parens(text: str) -> str:
    """Repair the parenthesis count left over by the regex simplifications."""
    depth = 0
    trimmed = []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                continue  # drop unmatched closer
            depth -= 1
        trimmed.append(ch)
    return "".join(trimmed) + ")" * depth


def _check_target_column(table: TableInfo, definition: str) -> Optional[ColumnInfo]:
    """Attach a CHECK to the single column it mentions (multi-column ones are skipped)."""
    mentioned = [c for c in table.columns if f"{c.name}" in definition]
    if len(mentioned) == 1:
        return mentioned[0]
    return None


# ---------------------------------------------------------------------------
# Legacy fallback (used only when the database cannot be reached at all)
# ---------------------------------------------------------------------------
LEGACY_SCHEMA_TEXT = """
Database: car_rental (PostgreSQL)

Tables:

locations(id, name, city, address, phone, created_at)
employees(id, location_id FK->locations, first_name, last_name, role, salary, hire_date, email, phone)
vehicle_categories(id, name, description, daily_rate_min, daily_rate_max)
vehicles(id, category_id FK->vehicle_categories, location_id FK->locations, make, model, year,
         license_plate, color, daily_rate, mileage, status)
clients(id, first_name, last_name, email, phone, drivers_license, date_of_birth, registration_date)
reservations(id, client_id FK->clients, vehicle_id FK->vehicles, pickup_location FK->locations,
             return_location FK->locations, pickup_date, return_date, status, total_cost)
payments(id, reservation_id FK->reservations, amount, payment_method, payment_date, status)
maintenance_records(id, vehicle_id FK->vehicles, maintenance_type, description, cost,
                    maintenance_date, mileage_at_service, completed)
reviews(id, reservation_id FK->reservations, rating, comment, review_date)
""".strip()
