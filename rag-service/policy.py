"""Application-level authorization by AST rewriting.

The generated SQL is parsed with ``sqlglot`` and the user's policy is *injected
into the tree* before execution:

* **row scoping** -- a per-(role, table) predicate is ANDed into the WHERE of
  every SELECT scope where the table appears, with the alias the query actually
  uses. Context values (``:location_id``) become literal AST nodes, so nothing
  is ever concatenated into a SQL string.
* **column denial** -- referencing a denied column (``employees.salary`` for a
  non-manager) blocks the request; ``SELECT *`` over a table with denied
  columns is rewritten to the explicit list of allowed columns instead of being
  rejected, so the user still gets a useful answer.

The policy lives in ``policy.yaml``; roles also carry the PostgreSQL role used
by the row-level-security layer (defense in depth, see ``04_rls.sql``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import sqlglot
from sqlglot import exp

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# User context
# ---------------------------------------------------------------------------
@dataclass
class UserContext:
    user_id: str = "anonymous"
    role: str = "manager"
    location_id: Optional[int] = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def value(self, key: str) -> Any:
        if key == "location_id":
            return self.location_id
        if key == "user_id":
            return self.user_id
        if key == "role":
            return self.role
        return self.attributes.get(key)

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "role": self.role,
            "location_id": self.location_id,
            "attributes": self.attributes,
        }


@dataclass
class RolePolicy:
    name: str
    description: str = ""
    row_filters: dict[str, str] = field(default_factory=dict)
    denied_columns: list[str] = field(default_factory=list)
    denied_tables: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)
    db_role: Optional[str] = None
    max_rows: Optional[int] = None

    def denies(self, table: str, column: str) -> bool:
        table = table.lower().split(".")[-1]
        column = column.lower()
        for entry in self.denied_columns:
            entry = entry.lower()
            if entry == f"{table}.{column}" or entry == f"*.{column}":
                return True
        return False

    def denied_columns_of(self, table: str) -> set[str]:
        table = table.lower().split(".")[-1]
        out = set()
        for entry in self.denied_columns:
            t, _, c = entry.lower().partition(".")
            if t in (table, "*"):
                out.add(c)
        return out


@dataclass
class PolicyResult:
    ok: bool
    sql: str = ""
    blocked_reason: Optional[str] = None
    applied_filters: list[dict] = field(default_factory=list)
    expanded_stars: list[str] = field(default_factory=list)
    role: str = ""

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "role": self.role,
            "blocked_reason": self.blocked_reason,
            "applied_filters": self.applied_filters,
            "expanded_stars": self.expanded_stars,
        }


class PolicyError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class PolicyEngine:
    def __init__(
        self,
        config: dict,
        catalog=None,
        dialect: str = "postgres",
    ):
        self.dialect = dialect
        self.catalog = catalog
        self.default_role = config.get("default_role", "manager")
        self.roles: dict[str, RolePolicy] = {}
        for name, raw in (config.get("roles") or {}).items():
            raw = raw or {}
            self.roles[name] = RolePolicy(
                name=name,
                description=raw.get("description", ""),
                row_filters=dict(raw.get("row_filters") or {}),
                denied_columns=list(raw.get("denied_columns") or []),
                denied_tables=list(raw.get("denied_tables") or []),
                requires=list(raw.get("requires") or []),
                db_role=raw.get("db_role"),
                max_rows=raw.get("max_rows"),
            )

    @classmethod
    def from_file(cls, path: str, catalog=None, dialect: str = "postgres") -> "PolicyEngine":
        import yaml

        with open(path, encoding="utf-8") as fh:
            config = yaml.safe_load(fh) or {}
        return cls(config, catalog=catalog, dialect=dialect)

    def role(self, name: str) -> RolePolicy:
        return self.roles.get(name) or self.roles.get(self.default_role) or RolePolicy(
            name=name
        )

    def db_role(self, ctx: UserContext) -> Optional[str]:
        return self.role(ctx.role).db_role

    def max_rows(self, ctx: UserContext) -> Optional[int]:
        return self.role(ctx.role).max_rows

    # -- main entry point -------------------------------------------------
    def rewrite(self, sql: str, ctx: UserContext) -> PolicyResult:
        policy = self.role(ctx.role)
        result = PolicyResult(ok=True, sql=sql, role=policy.name)

        if ctx.role not in self.roles:
            logger.warning(
                "unknown role '%s' -> falling back to '%s'", ctx.role, policy.name
            )

        for key in policy.requires:
            if ctx.value(key) in (None, ""):
                return PolicyResult(
                    ok=False,
                    blocked_reason=(
                        f"role '{policy.name}' requires '{key}' in the user context"
                    ),
                    role=policy.name,
                )

        try:
            tree = sqlglot.parse_one(sql, dialect=self.dialect)
        except Exception as exc:
            return PolicyResult(
                ok=False, blocked_reason=f"policy parse error: {exc}", role=policy.name
            )

        # 1. denied tables
        for table in tree.find_all(exp.Table):
            if table.name.lower() in {t.lower() for t in policy.denied_tables}:
                return PolicyResult(
                    ok=False,
                    blocked_reason=(
                        f"table '{table.name}' is not readable by role '{policy.name}'"
                    ),
                    role=policy.name,
                )

        alias_map = _alias_map(tree)

        # 2. star expansion where columns are hidden
        try:
            expanded = self._expand_stars(tree, policy, alias_map)
        except PolicyError as exc:
            return PolicyResult(ok=False, blocked_reason=str(exc), role=policy.name)
        result.expanded_stars = expanded

        # 3. explicit denied column references
        denied_hit = self._find_denied_column(tree, policy, alias_map)
        if denied_hit:
            return PolicyResult(
                ok=False,
                blocked_reason=(
                    f"column '{denied_hit}' is not readable by role '{policy.name}'"
                ),
                role=policy.name,
            )

        # 4. row scoping
        try:
            applied = self._apply_row_filters(tree, policy, ctx)
        except PolicyError as exc:
            return PolicyResult(ok=False, blocked_reason=str(exc), role=policy.name)
        result.applied_filters = applied
        result.sql = tree.sql(dialect=self.dialect)
        return result

    # -- steps ------------------------------------------------------------
    def _expand_stars(
        self, tree: exp.Expression, policy: RolePolicy, alias_map: dict[str, str]
    ) -> list[str]:
        expanded: list[str] = []
        for select in list(tree.find_all(exp.Select)):
            scope_tables = _scope_tables(select)
            if not scope_tables:
                continue
            sensitive = {
                real: policy.denied_columns_of(real)
                for _, real in scope_tables
                if policy.denied_columns_of(real)
            }
            if not sensitive:
                continue

            new_projections: list[exp.Expression] = []
            changed = False
            for projection in select.expressions:
                target_tables = _star_targets(projection, scope_tables)
                if target_tables is None:
                    new_projections.append(projection)
                    continue
                changed = True
                for alias, real in target_tables:
                    columns = self._allowed_columns(real, policy)
                    if columns is None:
                        raise PolicyError(
                            f"cannot expand '*' on '{real}': schema unknown, and the "
                            f"table has columns hidden from role '{policy.name}'"
                        )
                    expanded.append(real)
                    for col in columns:
                        new_projections.append(
                            exp.column(col, table=alias) if alias else exp.column(col)
                        )
            if changed:
                select.set("expressions", new_projections)
        return expanded

    def _allowed_columns(self, table: str, policy: RolePolicy) -> Optional[list[str]]:
        if self.catalog is None:
            return None
        info = self.catalog.table(table)
        if info is None:
            return None
        denied = policy.denied_columns_of(table)
        return [c.name for c in info.columns if c.name.lower() not in denied]

    def _find_denied_column(
        self, tree: exp.Expression, policy: RolePolicy, alias_map: dict[str, str]
    ) -> Optional[str]:
        referenced_tables = {real for real in alias_map.values()}
        for column in tree.find_all(exp.Column):
            if isinstance(column.this, exp.Star):
                continue
            col_name = column.name
            qualifier = (column.table or "").lower()
            if qualifier:
                real = alias_map.get(qualifier, qualifier)
                if policy.denies(real, col_name):
                    return f"{real}.{col_name}"
            else:
                # unqualified: fail closed if any table in scope hides it
                for real in referenced_tables:
                    if policy.denies(real, col_name):
                        return f"{real}.{col_name}"
        return None

    def _apply_row_filters(
        self, tree: exp.Expression, policy: RolePolicy, ctx: UserContext
    ) -> list[dict]:
        if not policy.row_filters:
            return []
        applied: list[dict] = []
        selects = list(tree.find_all(exp.Select))
        for select in selects:
            scope_tables = _scope_tables(select)
            for alias, real in scope_tables:
                template = _lookup_filter(policy.row_filters, real)
                if not template:
                    continue
                predicate = self._build_predicate(template, real, alias, ctx)
                select.where(predicate, copy=False)
                applied.append(
                    {
                        "table": real,
                        "alias": alias,
                        "predicate": predicate.sql(dialect=self.dialect),
                    }
                )
        return applied

    def _build_predicate(
        self, template: str, table: str, alias: Optional[str], ctx: UserContext
    ) -> exp.Expression:
        predicate = sqlglot.parse_one(template, dialect=self.dialect)

        # context placeholders -> literal AST nodes (never string interpolation)
        for placeholder in list(predicate.find_all(exp.Placeholder)):
            key = str(placeholder.this)
            value = ctx.value(key)
            if value is None:
                raise PolicyError(f"user context is missing '{key}'")
            placeholder.replace(_literal(value))

        # re-qualify the policy table with the alias used by the query
        if alias and alias.lower() != table.lower():
            for column in predicate.find_all(exp.Column):
                if (column.table or "").lower() == table.lower().split(".")[-1]:
                    column.set("table", exp.to_identifier(alias))

        return predicate


def _literal(value: Any) -> exp.Expression:
    if isinstance(value, bool):
        return exp.true() if value else exp.false()
    if isinstance(value, (int, float)):
        return exp.Literal.number(value)
    return exp.Literal.string(str(value))


def _lookup_filter(filters: dict[str, str], table: str) -> Optional[str]:
    plain = table.lower().split(".")[-1]
    for key, value in filters.items():
        if key.lower().split(".")[-1] == plain:
            return value
    return None


def _scope_tables(select: exp.Select) -> list[tuple[Optional[str], str]]:
    """(alias, real table) pairs directly in the FROM/JOINs of this SELECT."""
    out: list[tuple[Optional[str], str]] = []
    cte_names = set()
    parent = select
    while parent is not None:
        with_clause = parent.args.get("with") if hasattr(parent, "args") else None
        if isinstance(with_clause, exp.With):
            cte_names.update(cte.alias_or_name.lower() for cte in with_clause.expressions)
        parent = parent.parent

    sources: list[exp.Expression] = []
    # sqlglot renamed this argument ("from" -> "from_"), accept both
    from_clause = select.args.get("from_") or select.args.get("from")
    if isinstance(from_clause, exp.From):
        sources.append(from_clause.this)
    for join in select.args.get("joins") or []:
        sources.append(join.this)

    for source in sources:
        if isinstance(source, exp.Table):
            name = source.name
            if name.lower() in cte_names:
                continue
            out.append((source.alias or None, name))
    return out


def _alias_map(tree: exp.Expression) -> dict[str, str]:
    """alias (lowercased) -> real table name, over the whole statement."""
    mapping: dict[str, str] = {}
    for table in tree.find_all(exp.Table):
        name = table.name
        if table.alias:
            mapping[table.alias.lower()] = name
        mapping[name.lower()] = name
    return mapping


def _star_targets(
    projection: exp.Expression, scope_tables: list[tuple[Optional[str], str]]
) -> Optional[list[tuple[Optional[str], str]]]:
    """Return the tables a projection's star covers, or None if not a star."""
    if isinstance(projection, exp.Star):
        return scope_tables
    if isinstance(projection, exp.Column) and isinstance(projection.this, exp.Star):
        qualifier = (projection.table or "").lower()
        for alias, real in scope_tables:
            if qualifier in ((alias or "").lower(), real.lower()):
                return [(alias or real, real)]
        return scope_tables
    return None


DEFAULT_POLICY: dict = {
    "default_role": "manager",
    "roles": {"manager": {"description": "full access"}},
}
