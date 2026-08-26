# postgres MCP server

A [Model Context Protocol](https://modelcontextprotocol.io) server that exposes
the `car_rental` PostgreSQL database read-only: schema introspection plus a
single validated `run_query` tool. It uses the official Python MCP SDK's
`FastMCP`.

## Why this exists

This is the thesis's **baseline / comparison arm**. The project's real
contribution is `rag-service/` — a custom NL→SQL pipeline with curated
schema retrieval and self-repair logic. To argue that pipeline is worth
having, it needs to be measured against "what if we just handed the model
an MCP server and let it figure it out?" — the standard, idiomatic MCP
pattern with no bespoke retrieval or repair on top. That's what lives here.

So, deliberately:
- No query-repair loop, no schema retrieval/ranking, no prompt engineering
  beyond a short system instruction. `get_schema()` dumps the *entire*
  schema; the model decides what's relevant.
- No mutation tools. Every code path is read-only, enforced in three
  independent layers (see [Safety](#safety) below).
- Genuinely idiomatic: `FastMCP`, stdio transport, standard tool
  decorators — the same shape any MCP server for a SQL database would take.

## Tools

| Tool | Arguments | Returns |
|---|---|---|
| `list_tables()` | — | List of `{table_name, estimated_row_count}` for every table in `public` (row count from planner statistics, not `COUNT(*)`). |
| `describe_table(table_name)` | `table_name: str` | Columns (name/type/nullable/default/PK flag), primary key, outgoing + incoming foreign keys, CHECK constraints, up to 3 sample rows. |
| `get_schema()` | — | The whole schema as one compact DDL-ish text blob (all tables/columns/types/PK/FK) — the "dump everything into context" baseline. |
| `run_query(sql)` | `sql: str` | `{columns, rows, row_count, truncated, duration_ms}` for a single validated `SELECT` (or `WITH ... SELECT`). |

`describe_table` and `run_query` return `{"error": "..."}` instead of
raising an MCP-protocol-level error on invalid input, so the calling model
sees the problem and can retry with corrected arguments.

## Safety

Defense in depth — each layer is independent of the others:

1. **DB role**: connects as `readonly_user` (see
   `test_app_db/init/03_readonly_user.sql`), which only has `SELECT` grants
   in Postgres itself.
2. **Session**: every connection is opened with
   `default_transaction_read_only=on` and a `statement_timeout`, both set
   via connection options, so Postgres enforces them server-side regardless
   of what the submitted SQL tries to do.
3. **Statement validation**: `run_query` parses the SQL with **sqlglot**
   (not string/regex matching) and rejects it unless it is *exactly one*
   statement whose root is `SELECT`/`UNION`/`INTERSECT`/`EXCEPT`, with no
   `SELECT INTO`, no locking reads (`FOR UPDATE`/`FOR SHARE`), and no
   disallowed node anywhere in the parse tree — including inside a CTE
   (catches Postgres's data-modifying CTEs, e.g.
   `WITH x AS (DELETE FROM vehicles RETURNING *) SELECT * FROM x`, which a
   naive "starts with SELECT" check would miss). See
   `db.validate_readonly_sql` and `tests/test_validate_readonly_sql.py`.
4. **Result cap**: rows are capped at `MAX_ROWS` (default 100); the response
   reports `truncated: true` if more were available.

## Configuration

Copy `.env.example` to `.env` (or export the vars directly):

| Var | Default | Used by |
|---|---|---|
| `DATABASE_URL` | `postgresql://readonly_user:readonly_pass@localhost:5434/car_rental` | `db.py` |
| `MAX_ROWS` | `100` | `db.py` |
| `STATEMENT_TIMEOUT_MS` | `5000` | `db.py` |
| `GEMINI_API_KEY` | — | `llm_gemini.py` (only for `client_harness.py`) |
| `GEMINI_MODEL` | `gemini-2.5-flash` | `llm_gemini.py` |
| `MCP_HARNESS_MAX_ROUNDS` | `8` | `client_harness.py` |

`server.py` and `db.py` never import `google-generativeai` — the DB layer
has zero LLM/provider dependency. Only `client_harness.py` (via
`llm_gemini.py`) does.

## Files

```
mcps/postgres/
  db.py               connection + introspection + query execution — no MCP/LLM imports, usable standalone
  server.py           FastMCP tool registration (stdio transport) — thin layer over db.py
  llm_gemini.py        the ONLY module that knows about Gemini — isolated so a local model can be swapped in
  client_harness.py    spins up server.py over stdio + drives a Gemini tool-calling loop; what the eval harness imports
  requirements.txt     pinned deps (server + harness)
  requirements-dev.txt adds pytest
  Dockerfile
  .env.example
  tests/                pytest suite for the DB-independent logic (validator, JSON-safety, schema sanitizer)
```

## Running standalone

```bash
cd mcps/postgres
pip install -r requirements.txt
cp .env.example .env   # edit DATABASE_URL if not using the default port-5434 setup
python server.py
```

It speaks MCP-over-stdio and will just sit there waiting for a client to
connect — that's expected, it's not an HTTP service.

## Registering with Claude Desktop / Claude Code

Add to `claude_desktop_config.json` (Claude Desktop) or your MCP config
(Claude Code — `claude mcp add`, or the equivalent `.mcp.json`):

```json
{
  "mcpServers": {
    "car-rental-postgres": {
      "command": "python",
      "args": ["/absolute/path/to/mcps/postgres/server.py"],
      "env": {
        "DATABASE_URL": "postgresql://readonly_user:readonly_pass@localhost:5434/car_rental",
        "MAX_ROWS": "100",
        "STATEMENT_TIMEOUT_MS": "5000"
      }
    }
  }
}
```

Or, via the Docker image (see below):

```json
{
  "mcpServers": {
    "car-rental-postgres": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm", "--network", "natural-language-to-sql_default",
        "-e", "DATABASE_URL=postgresql://readonly_user:readonly_pass@test_app_db:5432/car_rental",
        "postgres-mcp"
      ]
    }
  }
}
```

## Using `client_harness.py` programmatically

This is the entry point the thesis's evaluation harness imports. It never
shells out — it uses the MCP SDK's `mcp.client.stdio` to spawn `server.py`
as a subprocess and speak MCP to it directly.

```python
from mcps.postgres.client_harness import ask, ask_async

result = ask("How many vehicles are currently available?")
# {
#   "question": "...",
#   "final_sql": "SELECT COUNT(*) FROM vehicles WHERE status = 'available'",
#   "columns": ["count"], "rows": [[7]], "row_count": 1,
#   "answer_text": "There are 7 vehicles currently available.",
#   "tool_calls": [ {"tool": "get_schema", "arguments": {}, "duration_ms": 4.1,
#                     "is_error": false, "result_preview": "..."},
#                    {"tool": "run_query", "arguments": {"sql": "..."},
#                     "duration_ms": 12.3, "is_error": false, "result_preview": "..."} ],
#   "latency_ms": 812.4,
#   "error": null
# }

# or from an already-async evaluator:
# result = await ask_async("...")
```

Also runnable directly for a quick manual check:

```bash
cd mcps/postgres
python client_harness.py "How many vehicles are currently available?"
```

Requires `GEMINI_API_KEY` in the environment. `client_harness.py` adds its
own directory to `sys.path`, so it works whether imported as a script
(`import client_harness`) or as a package
(`from mcps.postgres.client_harness import ask`, from the repo root — `mcps/`
has no `__init__.py`, so it's an implicit PEP 420 namespace package;
`mcps/postgres/` does).

## Testing

```bash
cd mcps/postgres
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

The suite (`tests/`) covers everything that doesn't require a live
database: the sqlglot statement validator (the accept/reject matrix
described under [Safety](#safety)), the Postgres-value-to-JSON converters,
and the MCP-JSON-Schema-to-Gemini-proto-Schema sanitizer. It does **not**
cover `list_tables`/`describe_table`/`get_schema`/`run_query`'s actual SQL
against a live Postgres, or `client_harness.py`'s live Gemini calls — those
need a running `test_app_db` and a `GEMINI_API_KEY` respectively; see
[Verifying against the live DB](#verifying-against-the-live-db).

## `docker-compose.yml` snippet

This repo's root `docker-compose.yml` isn't touched by this change (a
concurrent change was in flight there) — paste this service in yourself:

```yaml
  postgres-mcp:
    build: ./mcps/postgres
    container_name: postgres-mcp
    environment:
      DATABASE_URL: postgresql://readonly_user:readonly_pass@test_app_db:5432/car_rental
      MAX_ROWS: 100
      STATEMENT_TIMEOUT_MS: 5000
    depends_on:
      test_app_db:
        condition: service_healthy
    stdin_open: true   # MCP speaks over stdio, not a port — keep stdin open
    tty: false
```

Note this service has no meaningful long-running purpose under `docker
compose up` by itself (MCP stdio needs a client attached to its stdin/stdout,
which `docker compose up` doesn't provide) — it's built so an MCP client can
`docker run -i` or `docker compose run` it. If you want it evaluated as part
of the benchmark suite instead, run `client_harness.py` against the image
via `docker run -i --rm ... postgres-mcp` as the harness's server command.

## Verifying against the live DB

This was built and unit-tested in an environment with **no Docker/Postgres
available at all** (confirmed: no `docker`/`podman` binary, nothing
listening on 5432-5434, no local `postgres`/`psql`). Everything that
doesn't touch a real database was verified (see [Testing](#testing) and the
project report). What still needs a live check, once `test_app_db` is up:

```bash
# 1. bring up the DB (and everything else) as usual
docker compose up -d test_app_db

# 2. from mcps/postgres/, with deps installed:
python -c "import db; print(db.list_tables())"
python -c "import db; print(db.describe_table('vehicles'))"
python -c "import db; print(db.get_schema())"
python -c "import db; print(db.run_query('SELECT COUNT(*) FROM vehicles'))"

# 3. full MCP stdio round-trip:
python server.py &   # or just let a client spawn it
# (register it with Claude Code/Desktop as above, or drive it via client_harness.py)

# 4. end-to-end with Gemini (needs GEMINI_API_KEY):
python client_harness.py "How many vehicles are currently available?"
```
