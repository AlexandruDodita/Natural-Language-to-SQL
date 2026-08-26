# Oracle MCP Server

A read-only [MCP](https://modelcontextprotocol.io) server that lets an LLM explore and query
an Oracle schema safely. It exposes six tools — table listing, schema description, column
search, column statistics, foreign-key discovery, and an ad-hoc `SELECT` runner — behind a
SQL validation layer that rejects anything that is not a single read-only query.

Nothing in the code is tied to a particular schema: point it at any Oracle database via
`.env`.

## How it works

A request flows through four layers, each of which can reject it:

```
MCP client (Claude, etc.)
   │  Authorization: Bearer <token>
   ▼
BearerTokenMiddleware        mcp_server.py   — rejects unauthenticated requests
   ▼
tool function                mcp_server.py   — binds all user input as SQL *values*, never identifiers
   ▼
guards.validate_query()      guards.py       — parses the SQL; rejects anything but one read-only SELECT
   ▼
Oracle, as a read-only user  scripts/        — the real boundary: no write grants, no EXECUTE grants
   ▼
shaping.py                                   — serializes rows; caps cell and payload size
```

The layering is deliberate: **the database user is the actual security boundary, and the
guards are defense in depth.** A dedicated user with no `EXECUTE` and no write grants cannot
be talked into writing, no matter what SQL reaches it. The guards exist so that a malicious
query fails fast, loudly, and in the audit log — not because they are trusted to be perfect.

### The files

| File | Role |
| --- | --- |
| `mcp_server.py` | Tool definitions, bearer-token middleware, audit calls. Thin orchestration. |
| `guards.py` | SQL validation. Pure — never touches the database. |
| `shaping.py` | Row serialization, cell truncation, payload capping. Pure. |
| `oracle_conn.py` | Connection pool (created lazily), per-session `CURRENT_SCHEMA`. |
| `config.py` | All configuration, read from `.env`. Includes the SQL function allowlist. |
| `audit.py` | One JSON line per tool call, to a rotating log. |
| `scripts/create_readonly_user.sql` | Provisioning the read-only DB user. |

`guards.py` and `shaping.py` are pure by design — the test suite asserts that the driver is
never even imported — so the whole validation and formatting surface is testable without a
database.

### What `run_query` enforces

A query must be exactly one `SELECT` (a leading `WITH` is fine). Rejected: DML, DDL,
PL/SQL blocks, transaction control, semicolons, SQL comments, database links (`@`),
`DBMS_*`/`UTL_*`/`SYS.*` package references, and any function call not on the allowlist in
`config.ALLOWED_FUNCTIONS`.

That last one is the important one. Oracle lets a plain `SELECT` call a PL/SQL function,
and a definer's-rights function with an autonomous transaction can **write** from inside a
read-only query. So calls are allowlisted, not denylisted: only SQL-native built-ins
(`COUNT`, `TO_CHAR`, `JSON_VALUE`, …) may be invoked, and every schema- or package-qualified
call (`pkg.f(...)`) is refused outright.

Checks run against parsed tokens rather than raw text, so a string *value* like
`WHERE job = 'DBMS_SCHEDULER'` is fine while `DBMS_SCHEDULER.RUN(...)` as an *identifier* is
not.

### Results are shaped for a context window

`run_query` returns `{"rows": [...], "row_count": N, "truncated": bool}`. The row limit is
applied at fetch time (one row past the cap is probed, then discarded), so `truncated` is
exact — it distinguishes "exactly N rows exist" from "results were cut off", which tells the
model when to switch to `COUNT(*)` instead of paging blindly. The SQL itself is never
rewritten.

Oversized text cells are truncated with a marker, and if the response would still be huge,
trailing rows are dropped and reported. Duplicate column names (`SELECT a.id, b.id …`) are
preserved as `ID`, `ID_2`, `ID_3` rather than silently collapsing into one key.

## Plugging it into any Oracle database

**1. Install.**

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt   # POSIX: .venv/bin/pip
```

By default the driver runs in **thin mode** — no Oracle Instant Client needed, and it
speaks to Oracle Database 12.1+ directly. Set `ORACLE_LIB_DIR` to an
[Instant Client](https://www.oracle.com/database/technologies/instant-client.html)
directory only if you need thick-mode features; leaving it unset is the supported path
and the one the containerised setup uses.

**2. Create a read-only database user.** Edit `scripts/create_readonly_user.sql` — replace
`<SCHEMA_OWNER>`, `<PASSWORD>`, and list the tables to expose — and have a DBA run it.
Grant `SELECT` per table; never `SELECT ANY TABLE`, and never `EXECUTE` on anything.

This step is what actually makes the server safe. You *can* skip it and connect as the
schema owner, but then only the app-level guards stand between the model and your data.

**3. Configure.** Copy `.env.example` to `.env` and fill it in:

```ini
ORACLE_LIB_DIR=C:\path\to\instantclient_23_0
ORACLE_USER=mcp_readonly          # the read-only user from step 2
ORACLE_PASSWORD=...
ORACLE_HOST=...
ORACLE_PORT=1521
ORACLE_SERVICE_NAME=...
ORACLE_TARGET_SCHEMA=APP_OWNER    # the schema that OWNS the tables
MCP_AUTH_TOKEN=...                # python -c "import secrets; print(secrets.token_urlsafe(32))"
```

`ORACLE_TARGET_SCHEMA` is the one non-obvious setting. When you connect as a dedicated
read-only user, that user *owns nothing* — so the server reads `ALL_*` dictionary views
filtered on this schema, and sets `CURRENT_SCHEMA` on every pooled session so unqualified
table names in `run_query` still resolve. It defaults to `ORACLE_USER`, which is correct if
you connect as the schema owner.

Everything else is optional: `TABLE_DENYLIST` (comma-separated tables to hide from every
tool), `MAX_ROWS_HARD_CAP`, `QUERY_TIMEOUT_SECONDS`, `MAX_CELL_CHARS`, `MAX_RESPONSE_CHARS`,
`MCP_SERVER_NAME`, `MCP_HOST`, `MCP_PORT`, `AUDIT_LOG_PATH`.

**4. Run it.**

```bash
.venv\Scripts\python mcp_server.py
```

Defaults to streamable HTTP on `127.0.0.1:8000`. Set `MCP_TRANSPORT=stdio` for a
stdio-spawned client instead (see `claude_desktop_config.json`).

**5. Connect a client.** For Claude Code, a `.mcp.json` in the project root:

```json
{
  "mcpServers": {
    "oracle": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp",
      "headers": { "Authorization": "Bearer <MCP_AUTH_TOKEN>" }
    }
  }
}
```

> **Transport security.** The bearer token is sent in cleartext, so the server binds to
> loopback by default. Exposing it on a network address requires TLS in front of it — a
> reverse proxy terminating HTTPS is enough. Don't set `MCP_HOST=0.0.0.0` on a plain HTTP
> listener.

## Tools

| Tool | Purpose |
| --- | --- |
| `list_tables(keyword?)` | Tables in the target schema, with comments. Start here. |
| `search_columns(keyword)` | Find which table holds a concept, by column name or comment. |
| `describe_table(table)` | Columns, types, nullability, comments, PK, and FKs with targets resolved. |
| `list_related_tables(table)` | Incoming and outgoing foreign-key join paths. |
| `column_stats(table, column)` | Row/null/distinct counts, min/max, top values for low-cardinality columns. |
| `run_query(sql, max_rows?)` | Run a validated read-only `SELECT`. |

## Tests

```bash
.venv\Scripts\python -m pytest tests -q
```

The bulk of the suite is two catalogs in `tests/`: `cases_rejected.py` (malicious and
malformed SQL that must be refused, each with the reason it must be refused for) and
`cases_allowed.py` (legitimate queries — including trap words in safe positions — that must
*not* be refused). False positives are as much a bug as false negatives, so both directions
are pinned. Adding a guard means adding cases to both files.

## Auditing

Every tool call appends one JSON line to `logs/audit.log` (rotating, 10 MB × 5) with a
timestamp, the tool, the SQL or target, row count, duration, and outcome — `ok`,
`rejected:<reason>`, or `error:<type>`. Rejected queries are logged *with their reason*, so
the log shows what was attempted, not just what succeeded. It contains real query text and
is gitignored.
