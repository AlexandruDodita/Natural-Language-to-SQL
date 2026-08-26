# Design notes — retrieval, self-repair and authorization in the RAG service

These notes describe what was added to `rag-service/`, `test_app_db/` and why.
They are written to be quoted directly in the thesis chapters (architecture,
security, testing, evaluation).

The starting point was a 441-line `main.py`: a hard-coded schema string, one
Gemini call, a keyword blocklist, an execution through the Rust service, and an
SSE stream. Three things were missing for the thesis's own claims to hold:
there was no retrieval (despite the name and the RAG chapter), no correctness
loop, and no authorization (only a read-only database user, which prevents
writes but lets any user read every branch's salaries).

---

## 1. Module layout

`main.py` is now a thin FastAPI layer (routes, request models, SSE framing).

| Module | Responsibility |
|---|---|
| `config.py` | All settings from environment variables; `ablation_knobs()` is the subset the evaluation varies |
| `db.py` | Two execution back-ends (`HttpRunner` → Rust service, `DirectRunner` → psycopg) plus pure helpers (`parse_sql_response`, `extract_http_error`, `session_statements`, `to_jsonable`) |
| `schema_store.py` | Introspection queries + `build_catalog()` (pure) + the `SchemaCatalog`/`TableInfo`/`ColumnInfo` model, prompt rendering, disk cache |
| `retrieval.py` | Embedders (sentence-transformer / hashing), value index, `SchemaIndex` (ranking, FK expansion, persistence) |
| `validator.py` | sqlglot AST validation (allowlist-shaped) and the row cap |
| `policy.py` | Policy file model, `UserContext`, AST rewriting (row predicates, column denial, star expansion) |
| `llm.py` | Prompt construction + `LLMClient` interface, `GeminiClient`, `UnavailableClient` |
| `pipeline.py` | Orchestration: retrieve → generate → validate → authorize → dry-run → execute, with the repair loop |
| `telemetry.py` | `RequestTrace`, JSONL sink, aggregation for the results tables |
| `report.py` | Excel generation (unchanged behaviour, moved out of `main.py`) |
| `state.py` | Startup wiring: introspection, index build/load, policy load, LLM client |
| `eval/run_eval.py` | Retrieval ablation harness (offline) and telemetry aggregation |
| `policy.yaml` | The authorization policy (data, not code) |

Nothing about the external contracts changed: the SSE markers
(`[META]`, `[DATA]`, text chunks, `[DONE]`, `[ERROR]`) keep their order and
their original keys, and `POST /report` is byte-for-byte the same endpoint.
New keys were only *added* to `[META]`.

---

## 2. Schema retrieval (the missing "R" in RAG)

### 2.1 Introspection

At startup the service reads `pg_catalog` for tables, columns, types,
nullability, defaults, primary keys, unique constraints, foreign keys, CHECK
constraints, comments and row estimates. Nothing about `car_rental` is
hard-coded, so pointing `TARGET_DATABASE_URL` at another PostgreSQL database is
all that multi-database support requires — the thesis claim is now true rather
than aspirational.

Two robustness decisions:

* the catalog is cached at `INDEX_DIR/catalog.json`; if the database is
  unreachable at boot, the last known catalog is used, and if there is none the
  service falls back to a bundled schema text and still answers;
* CHECK constraints are normalised for the prompt
  (`CHECK (((role)::text = ANY ((ARRAY['manager'::character varying, …])::text[])))`
  becomes `CHECK(role IN ('manager', 'agent', …))`), which both shortens the
  prompt and makes the enumerated domains readable by the model.

### 2.2 Ranking

Each table is embedded once from a description built out of its name, comment,
columns, types, foreign keys and CHECK domains. A question is scored against
every table with three signals:

```
score = 1.0 · cosine(question, table)      # dense, local sentence-transformer
      + 0.6 · lexical(question, names)     # token overlap with table/column names
      + 0.8 · value(question, value index) # literals found in the question
```

The dense encoder is local (`all-MiniLM-L6-v2` by default, any
sentence-transformer via `EMBEDDING_MODEL`), never an API. When the package or
the model is unavailable the service degrades to a deterministic **hashing
embedder** — that is also the "no dense model" baseline of the ablation, and it
is what the test suite uses so results are reproducible without a download.

The index (embeddings + value index) is persisted to `INDEX_DIR/index.json` and
keyed on the catalog fingerprint and the embedder name, so it is rebuilt only
when the schema or the model changes.

### 2.3 Value index

Low-cardinality text columns are sampled (`LIMIT` on a subquery, then
`DISTINCT`, then a cardinality cut-off) and their values are indexed to
`table.column`. Columns above `VALUE_INDEX_MAX_DISTINCT` distinct values in the
sample are skipped, so nothing large is ever materialised — on `car_rental` this
yields 156 values and correctly links "Toyota" → `vehicles.make` and "Miami" →
`locations.city`. Matched values are also written into the prompt as hints.

### 2.4 Fallback and FK expansion

If the database has at most `RETRIEVAL_FALLBACK_MAX_TABLES` tables the whole
schema is injected (mode `full`) — for a 9-table demo database that is the
better trade-off, and the ablation can turn it off by setting the threshold to
0. Otherwise the top-k tables are injected (mode `topk`), optionally extended
with **join bridges**: tables that are foreign-key neighbours of at least two
selected tables. That is what stops "revenue per city" from retrieving
`payments` and `locations` without `reservations`.

### 2.5 Measurability

`RetrievalResult` always carries the full ranking with the three score
components, the matched values and the mode, even in `full` mode. It is exposed
per request in `[META].retrieval`, in the telemetry record, and standalone
through `POST /retrieve` — which is what makes schema-linking recall scoreable.

---

## 3. Execution-feedback self-repair

The loop in `pipeline.py`:

1. **retrieval** → schema text for the prompt;
2. **generation** → `{sql, reasoning, chart}` (or `{clarification}`, or `{refusal}`);
3. **validation** → sqlglot AST checks + row cap; failure feeds the validator
   error back and regenerates;
4. **authorization** → policy rewrite; a violation is **terminal** (see §4);
5. **dry run** → `EXPLAIN <sql>` through `DirectRunner`, which catches wrong
   column/table names, bad casts and ambiguous references *without executing*;
   failure feeds the exact PostgreSQL error back;
6. **execution** → through the Rust service (default) or psycopg;
   failure likewise feeds the exact error back.

The retry budget is `MAX_REPAIR_ATTEMPTS` (default 2, i.e. up to 3 generations).
Every attempt is recorded — index, stage, SQL, error — not just the final one.

Note that the dry run needs `TARGET_DATABASE_URL`: `EXPLAIN` cannot go through
`POST /api/sql`, which only accepts statements starting with `SELECT`. Without
a direct connection the stage is skipped and errors are caught at execution
instead.

### Ambiguity

The generation prompt allows a third answer shape: when several defensible SQL
queries would give different results (the thesis's own example, *"care sunt cei
mai buni clienți?"*), the model returns
`{"clarification": "…"}` instead of guessing. This is a distinct, observable
outcome: `[META].outcome == "clarification"`, `[META].clarification` carries the
question, no SQL is executed, and the clarifying question is streamed as normal
text so the existing frontend renders it unchanged.

A related failure was found during live testing and fixed: when no query is run,
the answering prompt used to still say *"you have access to live data"*, and the
model happily invented salary figures. The no-data path now uses a separate
anti-fabrication prompt, and a question that needs a column the role cannot read
produces `{"refusal": …}` → outcome `blocked_by_policy` instead of an invented
answer.

---

## 4. Authorization and resource limits

### 4.1 Application layer — AST rewriting (`policy.py`)

The generated SQL is parsed and the policy is injected into the tree:

* **Row scoping.** For every SELECT scope, each table in its `FROM`/`JOIN` that
  has a filter for the current role gets the predicate ANDed into that scope's
  `WHERE`, re-qualified with the alias the query actually uses
  (`vehicles.location_id = :location_id` becomes `v.location_id = 4` for
  `FROM vehicles v`). Subqueries are scoped independently.
* **Context values are literals.** `:location_id` is parsed as a placeholder
  node and replaced by a literal AST node built from the user context. A context
  value of `x' OR '1'='1` becomes the single string literal `'x'' OR ''1''=''1'`
  — there is no string concatenation anywhere in the path.
* **Column denial.** A reference to a denied column (qualified or not) blocks the
  request. Unqualified references fail closed: if *any* table in scope hides that
  column, the query is refused.
* **Star expansion.** `SELECT *` over a table with hidden columns is rewritten to
  the explicit list of allowed columns (using the introspected catalog) instead
  of being rejected, so the user still gets an answer.
* **Per-role row caps.** `max_rows` in the policy tightens the validator's LIMIT.

A policy violation is deliberately terminal — no repair attempt. Retrying would
amount to inviting the model to find a way around the rule; the user is told the
request was refused, and the event is recorded as `blocked_by_policy`.

The policy lives in `rag-service/policy.yaml` (roles `manager`, `agent`,
`analyst`, `auditor`). Adding a role is a data change, not a code change.

### 4.2 Database layer — RLS (`test_app_db/init/04_rls.sql`)

Independently of the application: three `NOLOGIN` roles (`app_manager`,
`app_agent`, `app_analyst`), row-level security on the seven data tables, and
policies keyed on the session GUC `app.location_id`, which the executor sets with
`set_config(…, is_local => true)` inside the transaction before `SET LOCAL ROLE`.
Salaries are additionally protected by column-level privileges, so even a query
that slipped past the application layer is rejected by the server.

Fail-closed by construction: with no `app.location_id`, the predicate is NULL and
an agent sees zero rows.

Backwards compatibility was a requirement: enabling RLS would otherwise hide
every row from `readonly_user`, which the current execution path uses, so
`readonly_user` gets an explicit permissive policy. Verified: it still sees all
40 employees and can read `salary`, exactly as before.

Resource limits are set at role level (no application change needed):
`statement_timeout = 5s`, `idle_in_transaction_session_timeout = 10s`,
`lock_timeout = 2s`, `default_transaction_read_only = on`,
`CONNECTION LIMIT 10`. The row cap is enforced in the application by injecting or
clamping `LIMIT`.

### 4.3 Validation — from blocklist to AST allowlist (`validator.py`)

`sqlparse` + a keyword blocklist is replaced by sqlglot AST checks:

| Check | Rationale |
|---|---|
| single statement | stacked `; DROP …` |
| root is a query (SELECT / WITH / set operation) | anything else refused |
| no DML/DDL node anywhere, no opaque `Command` | catches `COPY`, `SET`, `VACUUM`, DML inside CTEs |
| no `INTO`, no `FOR UPDATE` | write paths and locking |
| no `pg_*` / `information_schema` table | schema and credential probing |
| no `pg_*`, `lo_*`, `dblink*`, `set_config`, … function | file access, sleeps, configuration changes |
| every table exists in the introspected catalog | catches hallucinated tables before the database sees them |
| `LIMIT` injected or clamped to `max_rows` | resource exhaustion |

Two concrete improvements over the blocklist: `WHERE status = 'DELETE'` and a
column named `update_time` are no longer false positives, while
`WITH x AS (DELETE FROM clients RETURNING id) SELECT * FROM x` — which the
blocklist's "first keyword must be SELECT" rule let through — is now refused.
The dialect is a parameter (`SQL_DIALECT`), and the Oracle dialect is covered by
a test.

### 4.4 User context

`ChatRequest` gained an optional `user` field
(`{user_id, role, location_id, attributes}`). When absent, the server defaults
(`DEFAULT_USER_ROLE`, `DEFAULT_USER_LOCATION_ID`, `DEFAULT_USER_ID`) apply, so
the existing frontend keeps working with no change at all. A persona switcher in
`chat-app/` was left out on purpose (optional in the brief); the demo can be
driven with `curl` or by setting the server default.

---

## 5. Telemetry

One JSON object per request appended to `TELEMETRY_PATH`:

```
request_id, timestamp, question, user{role, location_id},
retrieval{mode, tables, expanded, ranking[{table, score, dense, lexical, value}], value_matches},
attempts[{index, stage, sql, ok, error}], final_sql, row_count,
outcome, clarification, policy{applied_filters, blocked_reason},
stages{retrieval, generation, validation, policy, dry_run, execution, answer},
retries, total_ms, knobs{…}, model
```

`GET /telemetry/summary` aggregates it (success rate, outcome counts, average
retries, repaired-after-retry count, blocked-by-policy count, average latency per
stage); `eval/run_eval.py --telemetry <file>` does the same offline.

Outcome vocabulary (closed, so results tables are a `GROUP BY`):
`answered`, `no_sql`, `clarification`, `blocked_by_policy`,
`validation_failed`, `execution_failed`, `generation_failed`.

---

## 6. Ablation knobs

All are environment variables; `GET /config` returns the effective values, and
every telemetry record embeds them, so a run can always be traced back to its
configuration.

| Knob | Env var | Default | What it varies |
|---|---|---|---|
| top-k tables | `RETRIEVAL_TOP_K` | 6 | prompt size vs schema-linking recall |
| fallback threshold | `RETRIEVAL_FALLBACK_MAX_TABLES` | 8 | whole schema vs top-k (0 = always top-k) |
| FK expansion | `RETRIEVAL_EXPAND_FK` | true | join-bridge tables added to the selection |
| value index | `VALUE_INDEX_ENABLED` | true | literal → column linking |
| embedder | `EMBEDDING_BACKEND` / `EMBEDDING_MODEL` | auto / all-MiniLM-L6-v2 | dense vs hashing baseline |
| retrieval on/off | `RETRIEVAL_ENABLED` | true | RAG vs full-schema prompt |
| retry budget | `MAX_REPAIR_ATTEMPTS` | 2 | self-repair depth |
| dry run | `DRY_RUN_ENABLED` | true | EXPLAIN before execution |
| clarification | `CLARIFICATION_ENABLED` | true | ask vs guess on ambiguity |
| policy | `POLICY_ENABLED` | true | authorization on/off |
| row cap | `SQL_MAX_ROWS` | 200 | result size |
| min score | `RETRIEVAL_MIN_SCORE` | 0.0 | rejecting weak matches |
| dialect | `SQL_DIALECT` | postgres | postgres / oracle |
| model | `GEMINI_MODEL` | gemini-2.5-flash | Gemini vs (later) a local model |

### Measured retrieval ablation

20 gold questions (`rag-service/tests/fixtures/schema_linking_gold.json`),
`car_rental` (9 tables), `RETRIEVAL_FALLBACK_MAX_TABLES=0` so top-k is always
active. `recall` = micro-average over gold tables, `coverage` = share of
questions whose gold tables are *all* retrieved. Reproduce with
`python eval/run_eval.py`.

| Embedder | Values | k | FK exp. | Recall | Coverage | Tables in prompt |
|---|---|---|---|---|---|---|
| hashing | on | 2 | no | 0.839 | 0.80 | 2.0 |
| hashing | on | 2 | yes | 0.903 | 0.85 | 2.4 |
| hashing | on | 3 | no | 0.871 | 0.85 | 3.0 |
| hashing | on | 3 | yes | 0.935 | 0.90 | 3.9 |
| hashing | on | 5 | no | 0.903 | 0.90 | 5.0 |
| hashing | on | 5 | yes | **0.968** | **0.95** | 6.0 |
| hashing | off | 3 | no | 0.806 | 0.75 | 3.0 |
| hashing | off | 3 | yes | 0.871 | 0.80 | 3.9 |
| MiniLM | on | 2 | no | 0.871 | 0.85 | 2.0 |
| MiniLM | on | 2 | yes | 0.935 | 0.90 | 2.4 |
| MiniLM | on | 3 | yes | 0.935 | 0.90 | 3.5 |
| MiniLM | on | 5 | yes | 0.935 | 0.90 | 6.0 |
| MiniLM | off | 2 | no | 0.806 | 0.75 | 2.0 |
| MiniLM | off | 3 | yes | 0.903 | 0.85 | 3.9 |

Readings: the value index is worth ~3–6 recall points; FK expansion is worth
~6 points at k=2 for ~0.4 extra tables in the prompt; the neural encoder helps
most at small k (0.871 vs 0.839 at k=2), which is exactly where prompt budget
matters. Retrieval latency: 0.2 ms (hashing) vs 5.7 ms (MiniLM, CPU) per
question — negligible next to generation.

### Measured stage latencies (live run, gemini-3-flash-preview, 12 requests)

| Stage | Average |
|---|---|
| retrieval | 0.4 ms |
| generation | 3 724 ms |
| validation | 2.4 ms |
| policy rewrite | 0.6 ms |
| dry run (EXPLAIN) | 3.1 ms |
| execution | 3.2 ms |
| answer streaming | 2 653 ms |

The entire added machinery costs about 10 ms per request; the LLM remains
~99 % of the response time, which confirms the earlier observation in the
thesis and means the safety layers are essentially free.

---

## 7. Configuration reference

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | — | from `VITE_GEMINI_API_KEY` |
| `GEMINI_MODEL` | `gemini-2.5-flash` | 2.0-flash returns HTTP 404 (retired); default is a stable release, not a preview |
| `SQL_BACKEND_URL` | `http://test_app_backend:8080` | Rust SQL executor |
| `TARGET_DATABASE_URL` | — | **new**: introspection, value index, EXPLAIN, RLS mode |
| `SQL_EXECUTOR` | `http` | `http` (unchanged path) or `direct` (psycopg + RLS) |
| `SQL_DIALECT` | `postgres` | sqlglot dialect |
| `SQL_MAX_ROWS` | `200` | injected/clamped LIMIT |
| `SQL_STATEMENT_TIMEOUT_MS` | `5000` | `SET LOCAL statement_timeout` in direct mode |
| `INDEX_DIR` | `/app/data/index` | catalog + embedding index cache |
| `INTROSPECT_SCHEMAS` | `public` | comma-separated |
| `EMBEDDING_BACKEND` | `auto` | `auto` / `sentence-transformers` / `hashing` |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | any local model |
| `RETRIEVAL_*`, `VALUE_INDEX_*` | see §6 | retrieval knobs |
| `MAX_REPAIR_ATTEMPTS`, `DRY_RUN_ENABLED`, `CLARIFICATION_ENABLED` | 2 / true / true | repair loop |
| `POLICY_ENABLED`, `POLICY_FILE` | true, `/app/policy.yaml` | authorization |
| `DEFAULT_USER_ID`, `DEFAULT_USER_ROLE`, `DEFAULT_USER_LOCATION_ID` | `demo`, `manager`, — | server-side defaults when the request omits `user` |
| `TELEMETRY_ENABLED`, `TELEMETRY_PATH` | true, `/app/data/telemetry.jsonl` | instrumentation |

New endpoints (all additive): `GET /config`, `GET /schema`, `POST /retrieve`,
`POST /validate`, `POST /admin/reindex`, `GET /telemetry/recent`,
`GET /telemetry/summary`.

---

## 8. docker-compose snippet (to merge by hand)

`docker-compose.yml` was intentionally not edited. The `rag-service` block
should become:

```yaml
  rag-service:
    build:
      context: ./rag-service
      args:
        WITH_EMBEDDINGS: "true"        # "false" -> small image, hashing embedder
    container_name: rag-service
    environment:
      GEMINI_API_KEY: ${VITE_GEMINI_API_KEY}
      GEMINI_MODEL: ${VITE_MODEL:-gemini-3-flash-preview}
      SQL_BACKEND_URL: http://test_app_backend:8080
      # new: introspection, value index, EXPLAIN dry-run, RLS session context
      TARGET_DATABASE_URL: postgresql://readonly_user:readonly_pass@test_app_db:5432/car_rental
      SQL_EXECUTOR: ${SQL_EXECUTOR:-http}          # 'direct' enables the RLS demo
      INDEX_DIR: /app/data/index
      TELEMETRY_PATH: /app/data/telemetry.jsonl
      POLICY_FILE: /app/policy.yaml
      # ablation knobs
      RETRIEVAL_TOP_K: ${RETRIEVAL_TOP_K:-6}
      RETRIEVAL_FALLBACK_MAX_TABLES: ${RETRIEVAL_FALLBACK_MAX_TABLES:-8}
      MAX_REPAIR_ATTEMPTS: ${MAX_REPAIR_ATTEMPTS:-2}
      DEFAULT_USER_ROLE: ${DEFAULT_USER_ROLE:-manager}
      DEFAULT_USER_LOCATION_ID: ${DEFAULT_USER_LOCATION_ID:-}
    volumes:
      - rag_data:/app/data
    ports:
      - "8100:8100"
    depends_on:
      test_app_backend:
        condition: service_started
      test_app_db:
        condition: service_healthy
    restart: unless-stopped
```

and at the bottom:

```yaml
volumes:
  postgres_data:
  test_app_db_data:
  rag_data:          # new: schema catalog, embedding index, telemetry
```

`04_rls.sql` only runs automatically on a **fresh** `test_app_db_data` volume.
On the existing volume, apply it by hand:

```bash
docker compose exec -T test_app_db \
  psql -U postgres -d car_rental < test_app_db/init/04_rls.sql
```

---

## 9. Tests

`pytest` from `rag-service/`. 180 tests run with no database and no API key
(179 passed + 1 skipped unless a sentence-transformer is installed); 15 more
need `TEST_DATABASE_URL`.

| File | Covers |
|---|---|
| `test_validator.py` (46) | accept/reject matrix, row cap, table extraction, Oracle dialect |
| `test_policy.py` (22) | row scoping, aliases, subqueries, column denial, star expansion, fail-closed, injection safety |
| `test_retrieval.py` (27) | ranking, value index, recall@k, FK expansion, modes, persistence, embedder fallback |
| `test_pipeline.py` (26) | repair loop, retry budget, dry run, clarification, refusal, policy termination, telemetry |
| `test_api.py` (17) | SSE framing and `[META]` keys, `/report` contract, user context |
| `test_schema_store.py` (20) | `build_catalog` (pure), CHECK simplification, fingerprint, caching |
| `test_db.py` (22) | response shaping, error extraction, session statements, JSON coercion |
| `test_live_db.py` (15) | live introspection, value sampling, EXPLAIN, statement timeout, RLS behaviour |

The committed fixture `tests/fixtures/car_rental_catalog.json` was produced by
running the real introspection against a live `car_rental`, and
`test_live_db.py::test_committed_fixture_matches_the_live_schema` keeps it
honest.

Retrieval ablation: `python eval/run_eval.py [--embedder …] [--no-values]
[--format latex]`.
