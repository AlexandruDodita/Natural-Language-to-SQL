# NL2SQL Workbench (frontend)

The React frontend for the natural-language-to-SQL system. It is a chat client
with a result workbench: every answer carries the query that produced it, the
result set, and the trace of how the pipeline got there.

The design is the one specified in [`docs/ui-redesign/PROPOSAL.md`](../docs/ui-redesign/PROPOSAL.md);
`docs/ui-redesign/mockup.html` is the static reference for it.

## What it shows

- **Workbench panel** with four tabs — Chart / Table / SQL / Provenance.
- **Provenance strip** on every answer: outcome, rows, SQL and total latency,
  attempt count, tables read, role — one click from the full trace.
- **Provenance tab** rendering what `telemetry.RequestTrace` already writes:
  stage latencies, the ranked retrieval list with scores, value-index hits,
  applied row filters, denied columns, `max_rows`, `request_id`.
- **Clarification card**: the readings the model proposed, each showing the
  measure expression it would aggregate on; picking one sends the disambiguated
  question.
- **Self-repair trail**: the failed attempt, the verbatim database error, and
  the attempt that succeeded.
- **Policy-block card**: distinct from an error. Names the role and the rule,
  and never offers "try again".
- **SQL tab**: Run / Explain / Format / Copy / Revert to generated. Running an
  edited query goes through `POST /execute` → `Pipeline.run_sql`, i.e. the same
  validator and policy rewrite as a generated one.
- **Interactive table**: sort, filter, group-by with sum, sticky header, per
  column type badge and value profile, `showing N of M`, truncation warning.
- **Chart toolbar**: the result shape line, ranked chart suggestions with the
  reason for each, then type / x / measures / split-by / right axis / stacked /
  100% / sort / top-N / moving average / trendline / bins.
- **Schema explorer** in the rail (`GET /schema`), with the tables retrieved for
  the active query highlighted.
- **Role selector** (`policy.yaml` roles, sent with every request), query history
  with re-run, board of pinned results, and a light/dark design system.

## Tech stack

- React 19 + TypeScript, Vite 7
- recharts for the chart marks, driven by one declarative `ChartSpec`
- Tailwind v4 is available, but the layout is the design-system CSS in
  `src/index.css` (tokens, primitives and breakpoints ported from the mockup)
- react-markdown for answer prose

## Project structure

```
src/
├── components/
│   ├── Board/BoardView.tsx           # pinned results, each with its own SQL and spec
│   ├── Chat/
│   │   ├── Stream.tsx                # the conversation
│   │   ├── Turn.tsx                  # one turn: prose, cards, result, provenance
│   │   ├── ProvenanceStrip.tsx
│   │   ├── ClarificationCard.tsx
│   │   ├── Notices.tsx               # repair trail, policy block, failures
│   │   └── ResultCard.tsx
│   ├── Composer/Composer.tsx
│   ├── Layout/
│   │   ├── AppLayout.tsx             # shell and application state
│   │   └── TopBar.tsx                # database, role, engine, view, theme
│   ├── Rail/                         # conversations, schema explorer, history
│   ├── Workbench/
│   │   ├── WorkbenchPanel.tsx        # the four tabs
│   │   ├── ChartPane.tsx             # suggestions + spec editor
│   │   ├── ChartView.tsx             # every chart type, from one spec
│   │   ├── TablePane.tsx
│   │   ├── SqlPane.tsx
│   │   └── ProvenancePane.tsx
│   └── ui/Toast.tsx
├── hooks/                            # useChat, useSchema, useTheme, useToast, useAutoScroll
├── lib/
│   ├── shape.ts                      # column typing, result profile, chart suggestions
│   ├── series.ts                     # sorting, top-N, pivoting, normalisation, binning
│   ├── format.ts                     # number/latency formatting, outcome labels, palette
│   └── sql.ts                        # formatter, CSV, clipboard, download
├── services/
│   ├── api.ts                        # /chat SSE, /schema, /roles, /execute, /report
│   └── backend-api.ts                # conversations, messages, stored artifacts
├── types/index.ts                    # the pipeline contract
└── index.css                         # design tokens, primitives, layout, breakpoints
```

## Getting started

```bash
npm install
cp .env.example .env
npm run dev
```

Environment:

| Variable | Default | Purpose |
|---|---|---|
| `VITE_RAG_URL` | `http://localhost:8100` | the RAG service (`/chat`, `/schema`, `/roles`, `/execute`, `/report`) |
| `VITE_MCP_URL` | `http://localhost:8300` | the MCP gateway (`/ask`), used by the MCP arm |
| `VITE_API_BASE_URL` | `http://localhost:8000` | conversation and message persistence |

`npm run build` type-checks and builds; `npm run lint` runs ESLint.

## Notes

- The target database is configured server side (`DATABASE_URL`); the top bar
  reports which one is connected rather than offering to switch it.
- Results and the full `sql_meta` are persisted per message, so reloading a
  conversation keeps its tables, charts and traces (TTL: `SQL_META_TTL_HOURS`).
- Keyboard: **Enter** sends, **Shift + Enter** inserts a newline.
- Theme, query history and the last chosen theme live in `localStorage`; the
  palette is defined once on `:root` / `:root[data-theme="dark"]`, so charts
  re-theme without a re-render.
