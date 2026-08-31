# UI redesign and chart-capability expansion

Two parts. Part 1 argues that the current chat UI throws away most of what the
pipeline already produces, and describes what `mockup.html` (in this folder)
does instead. Part 2 is the substantive one: a visualization and generation
capability set to replace the four-chart, one-x, one-y model the system has
today, with the files each proposal touches and a ranking by impact over cost.

Everything below cites the code as it stands. Open `docs/ui-redesign/mockup.html`
in a browser — it is a self-contained static file, no build step, no network —
and it is the reference for every UI claim.

---

## Part 1 — UI rationale

### 1.1 What the frontend is today

`chat-app` is ~1,900 lines of React. `AppLayout.tsx` is a three-column shell
(sidebar, chat, optional 480 px artifact panel). `useChat.ts` streams from
`POST /chat`, `api.ts` parses the SSE markers, `MessageBubble.tsx` renders a
turn, and `ArtifactPanel.tsx` shows a chart or a table with an Excel button.
The chart library actually in use is **recharts 3.8.1**
(`chat-app/package.json:17`), used only in `ArtifactChart.tsx`.

The backend is far richer than that. `pipeline.py` runs
retrieve → generate → validate → authorize → dry-run → execute with a repair
loop, and returns a `sql_meta` dict carrying `outcome`, `attempts`, `retries`,
`retrieval.{mode,tables}`, `policy.{role,filters,blocked_reason}`,
`clarification`, `request_id` and `role` (`pipeline.py:151-162`, `380-395`).
`telemetry.py` writes all of it plus per-stage latency to JSONL. `main.py`
additionally exposes `/schema`, `/retrieve`, `/validate`, `/config`,
`/telemetry/recent` and `/telemetry/summary` (`main.py:102-160`).

**The frontend consumes none of it.** `SqlMeta` has exactly four fields —
`sql`, `row_count`, `duration_ms`, `blocked` (`types/index.ts:1-6`) — so
`api.ts:111-119` parses the `[META]` frame and silently discards every other
key. That is the shape of the whole problem: the thesis's contributions are
measured in `benchmark/` and logged in `telemetry.jsonl`, but they are invisible
in the product.

### 1.2 Nine specific weaknesses

**W1 — The generated SQL is hidden behind a build flag, and showing it is
treated as an error.**
`MessageBubble.tsx:5` gates the SQL panel behind `VITE_DEBUG === 'true'`, so a
normal build never renders `SqlDebugPanel` (`MessageBubble.tsx:137`). Worse,
`MessageBubble.tsx:95-96` sets
`hasSqlLeak = /```sql/i.test(message.content)` and folds it into `isError`, so
if the model does mention SQL the turn is painted with the red error styling
(`MessageBubble.tsx:117`). For a text-to-SQL thesis the query *is* the artifact
under study; a user cannot verify an answer they cannot see, cannot correct a
subtly wrong join, and cannot reuse the query anywhere else.

**W2 — Seven distinct outcomes collapse into one apology string.**
`telemetry.py:26-32` defines `answered`, `no_sql`, `clarification`,
`blocked_by_policy`, `validation_failed`, `execution_failed`,
`generation_failed`. `useChat.ts:200` renders every failure as *"Sorry, there
was an error processing your request. Please try again."* A policy refusal
(which is terminal by design — `pipeline.py:266-296` never feeds it back to the
model) is indistinguishable from a transient network error, and "try again" is
actively wrong advice for it.

**W3 — The clarification turn arrives as prose, so the interpretations are not
actionable.**
`pipeline.py:394` puts the clarification into `sql_meta["clarification"]` and
`llm.py:76-80` asks the model to phrase it in natural language. Screenshot
`docs/screenshots/04-clarificare-intrebare-ambigua.png` shows the result: a
sentence offering three readings of "cei mai buni clienți", which the user must
answer by re-typing. This is the behaviour `benchmark/score.py:116-118` scores
as `ambiguous_clarified` and that `questions.yaml:382-420` dedicates four
questions to — the single most user-visible research contribution, rendered as
an ordinary paragraph.

**W4 — Results are not persisted; reloading a conversation loses every table
and chart.**
`MessageCreate.sql_meta` accepts only `sql_query`, `row_count`, `duration_ms`,
`blocked` (`backend-api.ts:18-24`), and `mapMessage` (`backend-api.ts:31-44`)
never reconstructs an `artifact`. The `columns`/`rows`/`chart` payload lives
only in React state (`useChat.ts:133-148`). Select another conversation and come
back and the artifact card is gone.

**W5 — The result table is a static `<table>`.**
`ArtifactTable.tsx` is 33 lines: no sorting, no filtering, no sticky header, no
column types, no pagination or virtualization, `white-space: nowrap` on every
cell and no height cap. `policy.yaml` allows `max_rows: 500` for manager and
analyst, and fleet-wide queries legitimately return dozens of wide rows;
the panel is 480 px wide and fixed (`AppLayout.tsx:65`), so wide results are
unreadable. `QueryResult.truncated` exists (`db.py:41`) and is never surfaced,
so a capped result silently looks like a complete one.

**W6 — One artifact at a time, desktop only.**
`AppLayout.tsx:10` holds a single `openArtifact`; opening a second result
replaces the first, so two queries can never be compared. The panel is
`hidden md:block` (`AppLayout.tsx:65`) — on a phone the chart and the table do
not exist at all.

**W7 — Authorization is implemented and unreachable.**
`policy.yaml` defines four roles with row filters and denied columns, enforced
twice (AST rewrite plus RLS). `main.py:84-86` accepts an optional `user` in
`ChatRequest`. `api.ts:62-69` sends `{messages}` only. The frontend has no role
selector, so the entire security chapter is undemonstrable in the product and
every request runs as the default `manager`.

**W8 — No schema affordance.**
`GET /schema` returns the full introspected catalog and `POST /retrieve` returns
the ranked tables with scores (`main.py:112-125`); neither is called. The empty
state says *"Ask me anything about SQL, databases, or data queries"*
(`MessageList.tsx:29-35`) against a database the user cannot see. On
AdventureWorks — 68 tables, 1,099 columns (`benchmark/datasets.py:86-102`) —
that is not a usable starting point.

**W9 — No design system, dark only.**
`index.css:13` hard-codes `background: #2d2d2d`; component colours are literal
hexes sprinkled through JSX (`#2d2d2d`, `#353535`, `#404040`, `#232323`,
`#1e1e1e`, `#1a1a1a` across `AppLayout`, `ChatArea`, `MessageBubble`,
`Sidebar`, `ArtifactPanel`). Text sizes are one-off (`text-[11px]`,
`text-[12px]`, `text-[13px]`, `text-[15px]`, `text-3xl`) and padding is set
inline in pixels (`MessageBubble.tsx:118-123`, `ChatInput.tsx:60-67`). There is
no light theme — a problem for a printed thesis, where dark screenshots are the
worst case. The chart palette is twelve shades of the *same* violet
(`ArtifactChart.tsx:10-14`), so a five-slice pie has no reliable category
separation, and none of it is colour-blind safe.

### 1.3 What the mockup changes

| # | Change in `mockup.html` | Fixes | Why it matters here |
|---|---|---|---|
| 1 | **Workbench panel with four tabs** — Chart / Table / SQL / Provenance | W1, W5 | The SQL is a first-class tab with Run, Explain, Format, Copy and *Revert to generated*; editing marks the result `edited` and the note explains that a re-run goes through the same validator and policy rewrite, so an edit cannot escalate privileges |
| 2 | **Provenance tab** | W2, W7, W8 | Renders exactly the fields `RequestTrace` already writes: outcome, stage-latency bar, the full ranked retrieval list with scores (retrieved tables highlighted), value-index hits, applied row filters, denied columns, `max_rows`, `request_id`. Nothing new is measured — it is surfaced |
| 3 | **Clarification card with clickable interpretations** | W3 | Each option shows the *measure expression* it would use (`SUM(p.amount) WHERE status='completed'` vs `COUNT(DISTINCT r.id)` vs `MIN(registration_date)`), plus a free-text escape. Choosing one records the reading next to the answer, so the query is reproducible — see thread "Care sunt cei mai buni clienți?" |
| 4 | **Provenance strip on every answer** | W2 | outcome · rows · SQL ms and total ms · attempt count · tables used · role, always visible, one click from the trace |
| 5 | **Self-repair trail** | W2 | Thread "Revenue 2024 vs 2023" shows attempt 1 failing at dry-run with the verbatim `column p.paid_at does not exist` hint and attempt 2 succeeding — the repair loop of `pipeline.py:297-363` made legible instead of hidden |
| 6 | **Policy-block card** | W2, W7 | Distinct from an error: names the role, the denied column and the `policy.yaml` rule, and offers *Retry as manager* / *Request access* / *Ask a permitted variant*. Never offers "try again" |
| 7 | **Role and dataset selectors in the top bar** | W7, W8 | `manager / agent / analyst / auditor` map 1:1 to `policy.yaml`; the DB selector matches `benchmark/datasets.py` |
| 8 | **Schema explorer in the rail** | W8 | Tables with row counts, expandable columns with types and PK/FK badges, a filter box, and the tables retrieved for the active query highlighted — `/schema` plus `/retrieve` finally rendered |
| 9 | **Interactive table** | W5 | Sort, filter, group-by with sum aggregation, sticky header, per-column type badge and a mini distribution profile drawn from the actual values, `showing N of M`, and the `max_rows` cap stated with a truncation warning |
| 10 | **Chart toolbar + suggestion ribbon** | §2 | The shape line (`10 rows · 1 categorical · 3 numeric · 0 temporal`) and ranked chart suggestions with the reason for each; then type, x, y, split-by, right axis, stacked, 100%, sort, top-N, moving average, trendline, bins |
| 11 | **Query history with re-run** | W4 | Stored SQL re-runs without a model call |
| 12 | **Board view** | W6 | Pinned results as tiles, each keeping its own SQL, filters and chart spec, plus a KPI tile derived from a pinned query rather than a re-typed number |
| 13 | **Design system** | W9 | Tokens for a 4 pt spacing scale, a 7-step type scale (11/12/13/15/18/22/30) and a full light + dark palette on `:root` / `:root[data-theme]`; an eight-hue categorical ramp instead of twelve violets; SVG marks use `var(--cN)` so charts re-theme without a re-render. Responsive at 1400 / 1180 / 820 / 560 px — below 1180 the workbench is an overlay, below 820 the rail is too, and both start closed so the conversation keeps the full width |

The mockup deliberately renders its charts with ~250 lines of hand-written SVG
rather than a library, to make one point: every chart type in Part 2 is drawn
from a single declarative spec. The production implementation should keep
recharts (or move to Vega-Lite, see P2) — but the spec, not the component, is
the interface.

---

## Part 2 — Chart and generation capability expansion

### 2.0 The constraint everything else follows from

The chart contract is one object with a type from a four-value enum, one `x`
string and one `y` string. It is stated four times and is identical in all four:

| Place | Code |
|---|---|
| Prompt | `llm.py:25` — `{"type": "bar\|line\|pie\|area\|none", "title", "x", "y"}` |
| Pipeline pass-through | `pipeline.py:196-201`, `425-431` |
| Excel writer | `report.py:19-24` `ChartConfig`, `33-38` `CHART_BUILDERS`, `75-102` single `Reference` |
| Frontend | `types/index.ts:8-13`, consumed at `ArtifactChart.tsx:24-33` |

`ArtifactChart.tsx:30-33` is the clearest symptom: it maps the result set down
to `{[chart.x]: row[xIdx], [chart.y]: row[yIdx]}` — **two columns survive,
everything else is discarded**. So `q36` (branch × credit_card / debit_card /
cash, 10×4) can only be drawn as one of its three measures, and `q34`
(month, revenue_2024, revenue_2023, yoy_pct, 12×4) can only show one line. The
MCP arm has its own separate, weaker inference: a regex over the *question text*
picking line/pie/bar (`mcps/postgres/gateway.py:37-72`), so the two arms are not
comparable on chart quality at all.

The benchmark inherits the same ceiling: `expected_chart` in
`benchmark/questions.yaml` only ever takes `none|bar|pie|line|area`, and
`report_score.py:99` maps exactly those four to openpyxl classes.

**One fact makes this cheap to fix.** `datasets.questions_fingerprint`
(`datasets.py:108-122`) hashes only `id`, `question` and `gold_sql` — its
docstring states outright that "a reworded note or a changed `expected_chart`
does not invalidate a stored answer". So the chart vocabulary can be extended
and the existing sweep results stay valid. Chart work does not cost a re-run of
the model comparison.

### 2.1 Foundations (everything else depends on these)

#### P1 · ChartSpec v2
**Question it answers** — none directly; it is what lets the rest exist.
**Shape** — universal.
**Change** — replace the flat object with:

```jsonc
{
  "type": "bar|hbar|line|area|combo|pie|scatter|hist|box|heat|facet|geo|kpi|waterfall|funnel|none",
  "title": "…",
  "x": "column",              // category / time axis
  "y": ["col", "col"],        // one or more measures
  "series": "column|null",    // long-format split (pivot on this column)
  "secondary": "column|null", // right axis
  "stacked": false, "normalize": false,
  "sort": "none|asc|desc", "topN": 0,
  "transform": { "resample": "D|W|M|Q", "agg": "sum|avg|median|count",
                 "movingAvg": 0, "compare": "none|prev_period|prev_year" },
  "overlay": { "trendline": false, "band": "none|ci95|iqr",
               "reference": [{"value": 0, "label": ""}], "outliers": "none|2sd|iqr" },
  "bins": 10
}
```

**Implementation** — `llm.py` (`CHART_RULES`, `SQL_INSTRUCTIONS:25`),
`pipeline.py:196-201` (validate the spec against the actual `result.columns`
before emitting it — today an invented column name silently produces a chartless
workbook, which `report_score.py:134-138` already has to work around),
`report.py` (`ChartConfig` + `build_excel`), `types/index.ts`,
`ArtifactChart.tsx`, and `benchmark/report_score.py:99` + `questions.yaml`
`expected_chart`.
**Thesis-relevant** — it is the precondition for measuring anything richer than
chart-class accuracy.

#### P2 · Column type and role metadata
**Question** — "is this column a date, a measure, or a label?"
**Shape** — universal.
**Today** — `QueryResult` carries `columns`, `rows`, `row_count`,
`duration_ms`, `truncated` (`db.py:36-50`) and no types, so both the frontend
and `gateway.py:25-34` sniff types by calling `float()` on strings.
**Change** — capture `cursor.description` type OIDs in the psycopg runner, map
to `{text, int, num, date, timestamp, bool}`, add `types: list[str]` to
`QueryResult.to_dict()` and to the `[DATA]` payload; classify each column as
`dimension | measure | time | key` (a `*_id` integer is a key, not a measure —
today a chart happily plots `client_id`).
**Implementation** — `rag-service/db.py`, `pipeline.py:425-431`,
`types/index.ts`, `mcps/postgres/db.py` for arm parity.
**Thesis-relevant** — makes P3 deterministic rather than heuristic.

#### P3 · Automatic chart-type inference from result shape
**Question** — "what should this result look like, without asking the model?"
**Shape** — decided *from* the shape; the rules, as implemented in the mockup
(`suggestions()`), are:

| Result shape | First suggestion | Alternatives |
|---|---|---|
| 1 row, 1 measure | `kpi` | — |
| time + 1..n measures | `line` | `combo` (mixed units), `area` |
| time + 1 dimension + 1 measure | `facet` | multi-`line`, `heat` |
| dimension (≤ 15 distinct) + 1 measure | `bar` / `hbar` if labels are long | `pie` if ≤ 6 slices and non-negative |
| dimension + n measures | grouped `bar` | stacked, 100 % stacked |
| ≥ 2 measures, ≥ 20 rows | `scatter` + trendline | `hist` |
| dimension matching `territory\|country\|region\|state\|province` | `geo` | `bar` |
| all-text | `none` | — |

**Domain example** — `q26` (`DATE_TRUNC('month', pickup_date)`, `COUNT(*)`,
12 rows) infers `line` with no model involvement; `q36` (10×4, one dimension and
three measures) infers stacked bars, which the current single-`y` contract
cannot express at all.
**Implementation** — new `rag-service/chart_infer.py` (pure, unit-testable),
called from `pipeline.py` after execution; `gateway.py:37-72` replaced by a call
to the same module so the RAG and MCP arms are finally comparable; add
`CHART_SOURCE=llm|rules|hybrid` to `Settings` and `ablation_knobs()`
(`config.py:142-159`), where `hybrid` = take the LLM spec, repair it against the
real column list, fall back to rules when it is unresolvable.
**Thesis-relevant, strongly.** This turns `report_score.py`'s
`chart_type_accuracy` into a *three-arm* comparison (model-chosen vs rule-based
vs hybrid) at zero extra sampling cost, since `questions_fingerprint` ignores
`expected_chart`. It is a self-contained evaluation chapter.

### 2.2 Chart types

#### P4 · Horizontal bars, sorting, top-N + "other"
**Question** — "who are the top 10, and how far ahead is number one?"
**Shape** — 1 dimension + 1 measure, long labels or > 8 categories.
**Example** — top clients by total spend: `Radu Constantinescu` on a vertical
axis is unreadable at the 480 px panel width; ranked horizontal bars are the
correct form. AdventureWorks `production.product.name` makes this acute.
**Implementation** — `ArtifactChart.tsx` (recharts `layout="vertical"`),
`report.py` (`BarChart.type = "bar"`), spec `sort` / `topN`.

#### P5 · Grouped, stacked and 100 % stacked bars
**Question** — "how does the mix differ between branches?"
**Shape** — 1 dimension + n measures, or 2 dimensions + 1 measure (pivot on
`series`).
**Example** — `q36` exactly: revenue per branch split into `credit_card`,
`debit_card`, `cash`. Stacked answers *level*, 100 % stacked answers *mix* — in
the mockup, cash share is highest at Constanța Port and lowest at Otopeni, which
only the 100 % view shows.
**Implementation** — `ArtifactChart.tsx` (multiple `<Bar>` with `stackId`),
`report.py` (`chart.grouping = "stacked"`, `overlap = 100`, one `Reference` per
measure), plus a long→wide pivot helper when `series` is set.

#### P6 · Dual-axis combo
**Question** — "revenue and growth rate on one picture."
**Shape** — time + ≥ 2 measures whose ranges differ by more than ~10×.
**Example** — `q34`: revenue in the tens of thousands and `yoy_pct` between 8
and 25. On a shared axis the percentage line is a flat smear on the baseline;
the mockup's "Revenue 2024 vs 2023" thread shows bars left, percentage right.
**Implementation** — `ArtifactChart.tsx` (recharts `ComposedChart` +
`YAxis yAxisId`), `report.py` (openpyxl `y_axis.axId` / `.crosses` for a
secondary axis), spec `secondary`.

#### P7 · Scatter and bubble
**Question** — "do these two measures move together?"
**Shape** — ≥ 2 measures and ≥ 20 rows.
**Example** — vehicle `mileage` vs lifetime `maintenance_cost`, coloured by
category (`vehicles` ⋈ `maintenance_records`). Today this shape has no
representation at all — the model must pick one measure and draw bars over 64
license plates.
**Implementation** — `ArtifactChart.tsx` (`ScatterChart`, `ZAxis` for bubble
size), `report.py` (`ScatterChart`), spec `x` as a measure rather than a
dimension.

#### P8 · Histogram and density, with a binning control
**Question** — "what does the distribution look like, not just the average?"
**Shape** — 1 measure, many rows.
**Example** — `q37` asks for a *median* rental cost per category precisely
because the mean misleads; a histogram of `reservations.total_cost` with the
median, Q1 and Q3 marked (as in the mockup) is the honest version of that
answer. AdventureWorks `salesorderheader.subtotal` is the same story.
**Implementation** — client-side binning in a new
`chat-app/src/lib/transform.ts` (bin count is a user control, not a guess),
`report.py` writes the binned table plus a bar chart.

#### P9 · Box plot / distribution by category
**Question** — "which category has the widest spread?"
**Shape** — 1 dimension + 1 measure with many rows per group.
**Example** — rental cost by `vehicle_categories.name`; AdventureWorks
`listprice` by `productsubcategory`.
**Implementation** — quartiles computed either in SQL
(`PERCENTILE_CONT … WITHIN GROUP`, which the schema already supports and `q37`
already exercises) or client-side; recharts has no box mark, so this needs a
custom SVG shape — the mockup shows the pattern.

#### P10 · Heatmap
**Question** — "where does the seasonality sit inside the categories?"
**Shape** — 2 dimensions + 1 measure, one of them time-like.
**Example** — branch × month reservation counts, or AdventureWorks category ×
month sales (both in the mockup).
**Implementation** — pivot helper + a custom SVG mark; Excel export degrades to
a conditional-format colour scale on the Data sheet, which openpyxl supports
natively (`ColorScaleRule`) and which is arguably *better* than an embedded
chart.

#### P11 · Small multiples (faceting)
**Question** — "do all four categories share the same shape?"
**Shape** — time + 1 dimension (≤ ~12 panels) + 1 measure.
**Example** — AdventureWorks monthly sales faceted by `productcategory`: Bikes
dominate the level, so a shared-axis multi-line hides everything else; four
panels on a shared scale show that all four share one seasonal shape while
Accessories grows fastest. Car rental: monthly reservations per branch.
**Implementation** — a grid of small charts driven by the same spec with
`facet: series`; Excel export writes one chart per panel on the Chart sheet.

#### P12 · Waterfall (period-over-period bridge)
**Question** — "what moved revenue from last year to this year?"
**Shape** — 1 dimension + a signed contribution measure.
**Example** — 2023 → 2024 revenue bridged by branch, or by payment method.
**Implementation** — derived from `compare: prev_year` (P16) plus a stacked bar
with an invisible base series; openpyxl supports the same trick.

#### P13 · Funnel / status flow
**Question** — "where do reservations drop out?"
**Shape** — 1 ordered dimension + 1 count.
**Example** — `reservations.status` is a CHECK-constrained enum
(`confirmed → active → completed`, with `cancelled`/`no_show` as leaks —
`test_app_db/init/01_schema.sql:77-78`), and the retrieval layer already
normalises CHECK domains into the prompt (`design-notes.md §2.1`), so the stage
order is *known*, not guessed. AdventureWorks: `salesorderheader.status`.
**Implementation** — small custom mark; low cost, narrow applicability.

#### P14 · Geographic maps
**Question** — "which regions are underperforming?"
**Shape** — a dimension whose values match a known region gazetteer + 1 measure.
**Example** — AdventureWorks has real geography:
`sales.salesterritory.name` (10 regions), `person.countryregion` (238 codes),
`person.stateprovince` (181, with `countryregioncode` and `territoryid`), and
`person.address.spatiallocation` — an actual point column, currently typed
`varchar(44)` in `benchmark_data/adventureworks_schema.sql:93`. Car rental has
only `locations.city` (10 Romanian cities), which is enough for a
proportional-symbol map but not a choropleth.
**Implementation** — staged. **Stage 1** (cheap, in the mockup): a tile
cartogram — equal-area tiles per region, colour-encoded, so small high-value
regions stay readable and no projection data is needed. **Stage 2**: bundle a
minified TopoJSON for country + US state and render a real choropleth; this
means shipping ~100 KB of geometry and a name-matching gazetteer, which is why
it ranks low on impact/cost. **Stage 3**: parse `spatiallocation` for point
maps.

#### P15 · KPI tile with sparkline and delta
**Question** — "just tell me the number."
**Shape** — 1 row × 1 measure, or 1 measure + a time series for context.
**Example** — 19 of the 51 benchmark questions have `expected_chart: [none]`
(`q01` "how many vehicles are available", `q05`, `q13`…). Today "none" means the
UI shows *no artifact at all* — the answer is a sentence and the Excel export is
a one-cell spreadsheet. A big number with the row count, the query time and,
where a time column exists, a sparkline and a period delta is strictly better
and costs almost nothing.
**Implementation** — `ArtifactChart.tsx` new branch, `report.py` writes a
formatted single-value cell. Note the scoring consequence: `report_score.py`
currently treats "no chart wanted" as trivially passing
(`report_score.py:176-179`); a `kpi` type would need its own expectation.

### 2.3 Transforms, interaction and composition

#### P16 · Time-series pack — resampling, moving averages, period-over-period
**Question** — "smooth this", "compare to last year", "show it monthly instead".
**Shape** — time + ≥ 1 measure.
**Example** — the benchmark already contains all three as *SQL* questions:
`q26` (monthly counts), `q34` (same-month-last-year change, with a documented
trap where models default to `LAG(1)` instead of `LAG(12)`), `q35`
(three-month trailing mean, with a trap where filtering before the window gives
January the wrong value). Offering these as **post-query controls** is the
strongest argument in this document: the user gets the right answer *without*
the model having to get the window frame right, and the two paths can be
compared directly on the same questions.
Also needed: calendar-spine gap filling. A month with no completed payment is
simply absent from a `GROUP BY DATE_TRUNC` result, and a line chart then draws a
straight segment across the hole as if the value had been interpolated. The
pattern is already in the question set — `q33` builds a `generate_series`
calendar spine to count idle days — but as a *chart* transform it belongs in the
UI, where the user can choose between "gap", "zero" and "carry forward".
**Implementation** — `chat-app/src/lib/transform.ts` for the client-side path;
optionally a `POST /transform` in `main.py` for large results. The comparison
"model writes the window function" vs "UI applies the transform" is a clean
experiment against `q26/q34/q35`.

#### P17 · Aggregation and binning controls
**Question** — "roll this up by category instead", "average, not sum".
**Shape** — any result with ≥ 1 dimension and ≥ 1 measure.
**Example** — the fleet query returns one row per vehicle; a `Group by category`
control (in the mockup's Table tab) turns 64 rows into 5 without a second model
call. Numeric binning turns `mileage` into bands.
**Implementation** — `transform.ts` + the table/chart panes; the grouping is
also what `series` needs for the long→wide pivot in P5.

#### P18 · Statistical overlays — trendline, bands, outliers, reference lines
**Question** — "is that a trend or noise?", "which vehicles are abnormal?"
**Shape** — scatter (trendline), time series (trend + band), any bar (reference
line).
**Example** — in the mockup, `maintenance_cost ~ mileage` gives an OLS fit of
0.031 per km with R² = 0.71 and rings the two vehicles beyond ±2σ of the
residuals; those are exactly the "which vehicles cost us money" questions the
domain invites. Reference lines: the `daily_rate_min`/`daily_rate_max` band per
category from `vehicle_categories`, drawn over actual `daily_rate` values — a
constraint that exists in the schema and is never shown.
**Implementation** — OLS and IQR/σ are ~40 lines in `transform.ts` (the mockup
has them); recharts `ReferenceLine`/`ReferenceArea` for the marks; the fit
statistics belong in the chart caption, not the tooltip.

#### P19 · Drill-down and cross-filtering
**Question** — "what is *inside* that bar?"
**Shape** — any chart with a categorical mark.
**Example** — click "Otopeni Airport" in the branch chart → the system generates
`… WHERE l.name = 'Otopeni Airport'` as a new turn, or filters the linked table
in place (both are in the mockup: click a bar, then *Drill down*).
**Implementation** — this is nearly free because the safety machinery already
exists: build the drill query by adding a predicate to the *validated* SQL's AST
with sqlglot (`validator.py` already parses it), then send it through the normal
`pipeline.run` path so validation, policy rewrite and the row cap all apply
unchanged. New: a `POST /drill` endpoint, or simply a synthesised follow-up
message.
**Thesis-relevant** — a click that produces auditable SQL is a much stronger
demonstration of the AST layer than a screenshot of a blocked query.

#### P20 · Dashboard composition from several queries
**Question** — "put the four numbers I check every Monday on one page."
**Shape** — n independent results.
**Example** — the mockup's Board: a revenue KPI derived from the pinned monthly
query (not re-typed), fleet mix, revenue by branch, fleet condition; each tile
keeps its own SQL, filters and chart spec and can be re-run independently.
**Implementation** — the largest piece of new backend work: a `dashboards` /
`tiles` table alongside `conversations` in `backend/app/models.py`, CRUD in
`crud.py`, routes in `main.py`, and re-execution of stored SQL through the
pipeline's validate→authorize→execute path (never raw). Because policy is
applied at execution time, the same board correctly shows different numbers to
an `agent` and a `manager` — which is a good demonstration in itself.

#### P21 · Export and report generation
**Question** — "send this to my manager."
**Today** — `POST /report` writes a two-sheet workbook: `Data` plus one `Chart`
(`report.py:58-106`), and `report_score.py` scores whether the workbook opens,
whether the chart class matches, and whether its `Reference` ranges point at the
right columns.
**Proposed** —
1. **Multi-chart workbook** — one chart per measure or per facet, a `Query`
   sheet carrying the SQL, the role, the row count and the timestamp
   (provenance travels with the file), and a `Notes` sheet with the model's
   answer text.
2. **PDF / PPTX brief** — chart image, headline number, the answer paragraph,
   and the SQL in an appendix. `python-pptx` is a small dependency;
   a print stylesheet is free.
3. **CSV / Parquet** for results too large for Excel — with
   `QueryResult.truncated` (`db.py:41`) finally shown to the user.
4. **Board export** — one sheet per tile plus a cover sheet (mocked up).
5. **Scheduled reports** — a stored board re-run on a cron and emailed; the
   execution path is already idempotent and read-only.
**Implementation** — `rag-service/report.py` (the request model gains the P1
spec and a `format` field), `main.py:263-276`, `ArtifactPanel.tsx` export menu.
Keep the current two-sheet output as the default so `report_score.py` keeps
scoring the same thing.

#### P22 · Extend the chart evaluation harness
**Question** — "did the system pick the *right* chart, not just a plausible
class?"
**Today** — `expected_chart` is a list of type names and `report_score.py:99`
knows four classes; a chart that picks the wrong column for `y` but the right
class scores as correct as long as the axes resolve.
**Proposed** — `expected_spec: {type: [...], x: col, y: [cols], series: col}`,
scored on three axes: type match, axis/measure match, and
"drawable" (columns exist in the actual result). Add the new types to
`CHART_CLASSES`. Report per-arm chart accuracy for `CHART_SOURCE=llm`,
`rules` and `hybrid`.
**Implementation** — `benchmark/report_score.py`, `benchmark/questions.yaml`,
`benchmark/questions_adventureworks.yaml`, `benchmark/tables.py` (a new column
in the LaTeX table). Remember `report_score.py:58` re-implements the product's
chart prompt for scoring, so `CHART_RULES` changes must be mirrored there.
**Thesis-relevant** — this is what converts the whole of Part 2 from product
work into a measurable contribution.

### 2.4 Ranking

Impact and cost are scored 1-5 (cost is engineering days-ish: 1 ≈ hours,
5 ≈ a week or more). "Ratio" is impact ÷ cost. **T** = thesis-relevant (produces
a claim or a measurement), **P** = polish (improves the product only).

| Rank | Proposal | Impact | Cost | Ratio | T/P |
|---:|---|---:|---:|---:|:--:|
| 1 | **P3** Rule-based shape inference + `CHART_SOURCE` ablation | 5 | 2 | 2.5 | **T** |
| 2 | **P1** ChartSpec v2 | 5 | 2 | 2.5 | **T** |
| 3 | UI-W1/W2/W3: SQL tab, outcome-specific states, clarification as choices | 5 | 2 | 2.5 | **T** |
| 4 | **P15** KPI tile for the 19 `expected_chart: [none]` questions | 4 | 1 | 4.0 | P |
| 5 | **P4** Horizontal bars, sort, top-N | 4 | 1 | 4.0 | P |
| 6 | **P2** Column type metadata | 4 | 2 | 2.0 | **T** |
| 7 | **P5** Grouped / stacked / 100 % | 4 | 2 | 2.0 | **T** |
| 8 | Provenance panel (render what `RequestTrace` already writes) | 4 | 2 | 2.0 | **T** |
| 9 | **P22** Evaluation harness extension | 4 | 2 | 2.0 | **T** |
| 10 | **P6** Dual-axis combo | 3 | 2 | 1.5 | **T** |
| 11 | **P16** Time-series pack (resample / MA / PoP / gap fill) | 5 | 3 | 1.7 | **T** |
| 12 | **P18** Statistical overlays | 4 | 2 | 2.0 | **T** |
| 13 | UI-W5: interactive table (sort/filter/group, truncation notice) | 4 | 2 | 2.0 | P |
| 14 | **P17** Aggregation / binning controls | 3 | 2 | 1.5 | P |
| 15 | **P7** Scatter / bubble | 3 | 2 | 1.5 | P |
| 16 | **P19** Drill-down and cross-filtering | 4 | 3 | 1.3 | **T** |
| 17 | **P21** Export upgrade (multi-chart, provenance sheet, PDF) | 4 | 3 | 1.3 | **T** |
| 18 | **P8** Histogram with binning | 3 | 2 | 1.5 | P |
| 19 | **P11** Small multiples | 3 | 3 | 1.0 | P |
| 20 | **P10** Heatmap | 2 | 2 | 1.0 | P |
| 21 | UI-W4: persist artifacts (schema + CRUD change) | 3 | 3 | 1.0 | P |
| 22 | **P9** Box plot | 2 | 3 | 0.7 | P |
| 23 | **P20** Dashboard composition | 4 | 5 | 0.8 | P |
| 24 | **P12** Waterfall | 2 | 3 | 0.7 | P |
| 25 | **P13** Funnel | 2 | 2 | 1.0 | P |
| 26 | **P14** Geo — stage 1 tile cartogram | 3 | 2 | 1.5 | P |
| 27 | **P14** Geo — stage 2/3 real choropleth + points | 3 | 5 | 0.6 | P |
| 28 | UI-W7: role selector wired to `ChatRequest.user` | 4 | 1 | 4.0 | **T** |
| 29 | UI-W8: schema explorer from `/schema` + `/retrieve` | 3 | 2 | 1.5 | **T** |
| 30 | UI-W9: token-based design system, light theme, safe palette | 3 | 2 | 1.5 | P |

### 2.5 Suggested order of work

1. **P1 + P2 + P3** together — one branch. They are the contract, and P3 is a
   publishable ablation on its own.
2. **The UI truth-telling set** — SQL tab, provenance panel, outcome-specific
   states, clarification-as-choices, role selector. All read-only against
   existing endpoints; no backend change beyond sending `user` in the request.
3. **P15, P4, P5, P6** — the chart types the current contract structurally
   cannot express, now cheap because P1 exists.
4. **P16 + P18** — the analytical layer, evaluated against `q26/q34/q35/q37`.
5. **P22** — re-score the stored sweep results with the extended vocabulary.
   No model calls needed: `questions_fingerprint` ignores `expected_chart`.
6. Everything else as time allows; **P14 stage 2** and **P20** last.
