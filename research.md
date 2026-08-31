# What makes text-to-SQL hard, and what this benchmark measures

Background research for the benchmark's second wave of questions. It records
why the first wave stopped discriminating, what the published literature says
survives at the frontier, and which of those findings this project's question
set can and cannot test. The question sets themselves are
`benchmark/questions.yaml` and `benchmark/questions_adventureworks.yaml`; this
file is the argument behind them.

## 1. The saturation problem

Measured on this repository, five hosted models against the two fixtures:

| model | car_rental (26 scored) | adventureworks (34 scored) |
| --- | --- | --- |
| gemini-3.7-flash | 100% | 100% |
| gemini-3.6-flash | 100% | 100% |
| gemini-3.1-pro-preview | 100% | 100% |
| gemini-3-flash-preview | 100% | 100% |
| gemini-2.5-flash | 96.2% | 97.1% |

Four of five models are perfect on both. A benchmark on which the systems under
comparison all score 100% has stopped measuring them: the difference between
the naive whole-schema arm, the retrieval pipeline and the MCP agent cannot
appear in a number that is pinned to its ceiling.

The instinct is that this is a schema-size problem, and the AdventureWorks
fixture was built to test exactly that: 68 tables against 9, 1,099 columns
against ~70, a schema prompt 9x larger. It changed nothing. The 7.5x larger
schema cost 5.1x the prompt tokens and 2.3-2.8x the money and did not move
accuracy at all.

That negative result is worth reporting on its own, and the literature predicts
it. "The Death of Schema Linking?" (arXiv:2408.07702) argues that with
long-context models, feeding the whole schema outperforms retrieving a subset,
because retrieval's recall errors cost more than the extra context does. On a
68-table schema that still fits comfortably in context, there is nothing for
retrieval to win.

So the difficulty has to come from somewhere else.

## 2. Where the difficulty actually is

### Spider 2.0: the same problem, solved once already

Spider 2.0 (arXiv:2411.07763, ICLR 2025) exists because Spider 1.0 saturated at
~91% execution accuracy. At release, Spider 2.0 dropped an o1-preview-based
agent to **21.3%**. It is the closest available precedent for what this section
is doing, and its design choice is the load-bearing finding:

> Spider 2.0's difficulty premium comes primarily from query *shape*, not schema
> size. Its gold SQL averages **144.5 tokens** against BIRD's **30.9**.

Their error analysis over 300 failures gives the best public taxonomy of what
survives at the frontier:

| failure class | share |
| --- | --- |
| Erroneous data analysis | **35.5%** |
| — of which: intricate query planning | 17.7% |
| — of which: dialect/function misuse | 10.3% |
| — of which: advanced data calculation | 7.5% |
| Wrong schema linking | 27.6% |
| JOIN errors | 8.3% |

*Intricate query planning* — the largest single sub-class — is the model
emitting a **structurally simpler query than the task requires**: fewer
aggregation levels than the measure needs, a missing CTE stage, a collapsed
subquery. Their flagship failure case is a weekly-cohort retention query that
the model flattened into a single aggregate and then sorted by raw count
instead of by the retention *ratio*.

Note the ordering. Schema linking — the thing a 68-table fixture tests, and the
thing a RAG pipeline exists to improve — is 27.6%. Query planning and
calculation together are 35.5%. This benchmark measured only the smaller half.

### BIRD: grounding is the plateau, but not on a 9-table schema

BIRD (arXiv:2305.03111) has sat roughly 11 points below human performance
(81.95% best vs 92.96% human) for about a year. Its own taxonomy attributes
~82% of residual errors to schema and value *grounding* rather than exotic SQL.

That cuts both ways here. BIRD's databases are dirty, large and
under-documented, so grounding dominates. `car_rental` is nine clean tables
with a documented schema in the prompt; grounding is free. The corollary is
that on a fixture like this one, query shape is the *only* remaining axis, and
a question set that does not exercise it measures nothing.

### The constructs that break things, and why they escape most benchmarks

NL2SQL-BUGs (arXiv:2503.11984, KDD 2025) annotates 2,018 semantic errors and
reports a finding that matters more than its taxonomy: LLMs are near chance at
*detecting* semantic SQL errors — 75.2% on a set with a 50.5% base rate.
Semantic bugs execute cleanly and survive the model's own review.

Archer (arXiv:2402.12554, EACL 2024) isolates arithmetic reasoning and drops
GPT-4-era systems to 6.7% execution accuracy.

BIRD-CRITIC / SWE-SQL (arXiv:2506.18951) tests fixing real SQL issues rather
than writing queries: best model 38.9% against 78.9% human.

The specific traps the second wave is built on — fan-out double-counting,
`NOT IN` against a nullable column, integer division, the default `RANGE` window
frame, `RANK` vs `DENSE_RANK` vs `ROW_NUMBER` on real ties, gaps-and-islands —
are well-documented production failure modes but appear in **no** academic
benchmark as isolated, separately-scored categories. They share one property
that makes them worth building a benchmark on:

> The wrong query executes cleanly and returns plausible numbers.

A wrong query that raises a syntax error needs no benchmark to catch. Execution
accuracy — the metric this harness already uses — is the only thing that catches
a query which runs, returns 17 tidy rows, and is wrong in all of them.

### A warning that shaped the method

"Text-to-SQL Benchmarks are Broken" (Jin et al., CIDR 2026) measured annotation
error rates of **52.8%** in BIRD Mini-Dev and **66.1%** in Spider 2.0-Snow —
mostly gold-SQL/data mismatches and ambiguous questions with a single arbitrary
gold answer.

This is the trap that any attempt to make a benchmark harder walks into: hard
questions measure annotation noise unless the gold is verified against the real
data and every open reading is pinned. This project already learned the same
lesson empirically. The first draft of the AdventureWorks set left projections
open and scored gemini-2.5-flash at 69%, where every single miss was a
projection mismatch and not one was a wrong join; car_rental had the same defect
in eight questions, and fixing it moved the hosted models from 80.8-96.2% to
96.2-100% and shrank the six-run spread on gemini-2.5-flash from 11.5 points to
3.8. Most of what `variance.py` was reporting as sampling noise was the model
re-guessing an under-specified question.

Hence the two rules the second wave keeps:

1. **Difficulty comes from the SQL, never from ambiguity about what is asked.**
   Every question names its output columns and pins any measure with more than
   one defensible reading.
2. **Every gold query is executed against the real fixture** and must return a
   non-empty, non-degenerate result. Where the wrong variant was also executed
   and diffed, the trap comment says "verified".

## 3. What the first wave was missing

Diagnosed against the actual files and the actual seed data:

- **No question could double-count.** Payments are strictly 1:1 with
  reservations in the `car_rental` seed, so even a careless fan-out join cannot
  inflate a measure. The single most common silent analytical-SQL bug was
  unmeasurable by either set. (For scale: the naive single-`FROM` version of
  "revenue and maintenance cost per make" returns **$4,797,624** against a
  correct **$951,911**, and executes without complaint.)
- **The `window` category barely used windows.** car_rental's q26 was a plain
  `GROUP BY` time series with no window function at all. No `LAG`/`LEAD`, no
  frame clause, no `RANK`/`DENSE_RANK`/`ROW_NUMBER` distinction — the seed had
  no ties, which makes all three interchangeable.
- **No NULL semantics anywhere.** The car_rental seed has zero NULLs in any
  analytically meaningful column; AdventureWorks q37 was the single question in
  either set touching NULL-aware aggregation.
- **No question needed more than one CTE**, a self-join, a set operation, a
  calendar spine, a percentile, a pivot, a cohort, an interval-overlap test, or
  a ratio of aggregates.
- **The ambiguous questions were trivially ambiguous.** "How is the business
  doing?" and "Hello, what can you do?" are detectable by keyword filter. None
  had the property that makes ambiguity actually dangerous: looking answerable
  enough that a competent model plausibly barrels through.

## 4. The categories the second wave adds

Each is a construct with a characterisable wrong answer. The parenthetical is
the failure it detects.

| category | construct | what the wrong query does |
| --- | --- | --- |
| `multi_level_agg` | two measures over two fan-outs of one dimension | one `FROM` multiplies each measure by the other's row count |
| `temporal` | period-over-period | `LAG(x, 1)` compares to the preceding row, not the same period a year back |
| `calendar` | date spine | periods with no rows vanish instead of reporting zero |
| `cohort` | retention against acquisition period | cohorts on the wrong anchor date; ranks by count, not ratio |
| `pivot` | conditional aggregation to columns | returns long format — right numbers, wrong shape |
| `percentile` | interpolated median | `AVG` instead; or `PERCENTILE_DISC` instead of `_CONT` |
| `ratio` | ratio of sums | average of per-row ratios, which weights small rows equally |
| `set_ops` | `EXCEPT` / `INTERSECT` over cohorts | reads "both A but not B" as "A or B" |
| `self_join` | interval overlap | counts each unordered pair twice |
| `anti_join` | `NOT IN` vs `NOT EXISTS` | one NULL in the subquery makes the whole result empty |
| `gaps_islands` | consecutive-run detection | duplicate dates shift the row-number offset |
| `recursive` | multi-level hierarchy traversal | single-level join, where the data needs 178 rows not 3 |

They are additive: `score.py` groups whatever categories it finds, so the
harness needed no change. `tables.py` maps them onto three table columns —
`structure`, `measure`, `time` — because sixteen columns is not a table anyone
reads; the results files keep the ungrouped per-question category, so a
different cut costs an edit and no re-running.

## 5. What this fixture still cannot test

Recorded so the thesis can state the limits rather than imply there are none.
The `car_rental` seed cannot support:

1. **Recursion.** `employees` has no `manager_id`, so there is no hierarchy.
   One nullable self-referencing column and ~40 `UPDATE`s would give three
   levels.
2. **NULL semantics.** `reservations.total_cost`,
   `maintenance_records.mileage_at_service` and `vehicles.color` are 100%
   populated despite being nullable, so the `NOT IN` trap, `COUNT(col)` vs
   `COUNT(*)`, and AVG-skips-NULLs have no car_rental equivalent. They are
   tested on AdventureWorks only.
3. **Payment-side fan-out.** Payments are exactly 1:1 with reservations and the
   amount always equals `total_cost` — no deposits, no partial payments, no
   reservation paid twice. This is why the fan-out questions route through
   `maintenance_records` instead. Splitting ~200 reservations into a deposit
   plus a balance would also make "revenue" and "reservation value" diverge,
   which is new ambiguity material.
4. **Dead enum values.** No reservation is ever `'active'` and no employee is a
   `'mechanic'` or `'receptionist'`, although the CHECK constraints advertise
   them. A question filtering on those returns an empty gold result, which the
   scorer treats as trivially matchable.

AdventureWorks needs no additions; every second-wave question there was verified
against the loaded database as-is.

A further open question concerns the ambiguity metric rather than the data:
`run.py` scores ambiguous questions as asked-vs-guessed, which is binary. The
second wave's ambiguous questions are deliberately tempting to answer, and a
model that answers *with an explicitly stated assumption* currently scores the
same zero as one that answers silently. Those are not the same behaviour and
arguably should not score the same.

## Sources

- Spider 2.0 — https://arxiv.org/abs/2411.07763 · https://spider2-sql.github.io/
- BIRD — https://arxiv.org/abs/2305.03111 · https://bird-bench.github.io/
- BIRD-CRITIC / SWE-SQL — https://arxiv.org/abs/2506.18951 · https://bird-critic.github.io/
- NL2SQL-BUGs — https://arxiv.org/abs/2503.11984
- Archer (arithmetic reasoning) — https://arxiv.org/abs/2402.12554
- The Death of Schema Linking? — https://arxiv.org/abs/2408.07702
- BEAVER (enterprise schemas) — https://arxiv.org/abs/2409.02038
- Text-to-SQL Benchmarks are Broken, CIDR 2026 — https://www.vldb.org/cidrdb/papers/2026/p5-jin.pdf
- In-context-learning error types — https://arxiv.org/abs/2501.09310
- EDBT 2025, SQL understanding — https://openproceedings.org/2025/conf/edbt/paper-211.pdf

---

# Second-wave results (measured 2026-08-30)

The questions of §4 were added to both sets and every reachable arm re-run.
`car_rental` went 30 -> 51 questions (44 scored, 7 ambiguous); `adventureworks`
went 38 -> 56 (49 scored, 7 ambiguous).

## Execution accuracy: the ceiling moved, but did not break

| model | car_rental before | after | adventureworks before | after |
| --- | --- | --- | --- | --- |
| gemini-2.5-flash | 96.2% | **88.6%** | 97.1% | **91.8%** |
| gemini-3-flash-preview | 100% | **97.7%** | 100% | **98.0%** |
| gemini-3.1-pro-preview | 100% | 100% | 100% | 100% |
| gemini-3.6-flash | 100% | 100% | 100% | **98.0%** |
| gemini-3.7-flash | 100% | 100% | 100% | 100% |

Reported plainly: three of five models still answer every scored car_rental
question. The set now separates gemini-2.5-flash decisively and nicks the two
flash-preview models, but the strongest models solve fan-out, cohort, pivot,
calendar and set-operation questions correctly on the first attempt. Their SQL
was inspected rather than assumed - gemini-3.7-flash answered the fan-out
flagship with two separate aggregate subqueries LEFT JOINed onto a `DISTINCT
make` spine, which is the textbook-correct shape.

Twelve misses across ten runs, concentrated in three places:

- **window frame semantics** - AW q53 missed by 2/5, car_rental q35 by 1/5:
  filtering to the reporting year *before* the window truncates the frame.
- **dialect misuse** - two misses were `round(double precision, integer) does
  not exist`, the two-argument `round` that needs `numeric` in PostgreSQL. This
  is Spider 2.0's second-largest sub-class (10.3%) reproducing exactly.
- **cohort anchoring** - car_rental q41 missed by 2/5, the highest-scoring
  car_rental discriminator, and the same failure Spider 2.0 reports as its
  flagship case.

## The agentic arm is hit far harder than the one-shot arm

| arm | before | after |
| --- | --- | --- |
| `naive` (whole schema, one call) | 100% | 100% |
| `mcp-postgres` (agentic, same model family) | 92.3% | **79.5%** |

This is the most useful accuracy result of the second wave, and it inverts the
intuition that an agent which can inspect the live database should do better
than one shown a static schema. On the easy set the two were 8 points apart; on
the hard set they are 20. An agent that explores has more ways to go wrong: it
sees `maintenance_records` and reaches for it where the gold reads
`vehicles.status`, and each extra tool round is another chance to drift from
the question. Whole-schema prompting is not the weak baseline the pipeline was
built to beat - on this hardware and these schema sizes it is the arm to beat.

## Ambiguity: where the discrimination actually is

Scored on whether the system asked instead of guessing:

| question | asked / 5 models |
| --- | --- |
| q30 "Hello, what can you do?" | 5/5 |
| q28 "Show me the good vehicles." | 4/5 |
| q29 "How is the business doing?" | 3/5 |
| q27 "Care sunt cei mai buni clienți?" | 1/5 |
| **the six new subtle ones (car_rental q49-q51, AW q54-q56)** | **0/5** |

Every model answered every subtly-ambiguous question without asking, on both
databases, unanimously. The pattern is sharp: ambiguity that *announces itself*
lexically - a question with no metric in it at all, or no SQL to write - is
caught; ambiguity that hides behind an answerable-looking sentence is not.
"What is our average revenue per client?" has three defensible denominators in
this schema and every model silently picked one.

This is a cleaner result than the accuracy table and it is the one worth
building on, because it is a *capability* gap rather than a difficulty knob:
the models are not failing to write the SQL, they are failing to notice that
the question does not determine which SQL to write. It also has a direct
consequence for the thesis's own system, whose clarification behaviour is a
design feature rather than an emergent one.

The caveat from §5 applies with force here: `run.py` scores this binary, so a
model answering *with an explicit stated assumption* is scored identically to
one answering silently. Before this becomes a headline number, that distinction
should become a third outcome.

## Excel report quality is unaffected

Chart-type accuracy stayed at 100% for four of five models (gemini-3.1-pro at
97.7%) and structural validity at 100% across all five, on the enlarged set.
The harder SQL did not make chart selection harder, which is expected: the
chart follows from the shape of the result set, and the second wave did not
change result shapes much.

## Measurement inventory

What has actually been measured against the current question sets, and what has
not. The tables above cover only the **current** rows; everything else in
`benchmark/results/` describes the superseded 26/34-question sets and is not
comparable with them. `tables.py` marks the difference with a `*` and lists the
files, so this section is a summary of what that tooling reports, not a
substitute for running it.

**Current** (fingerprints `86e194123bb3` car_rental, `5398f281a907` adventureworks):

| what | files | status |
| --- | --- | --- |
| `naive`, 5 hosted models, car_rental | `naive-gemini-*.json` | done |
| `naive`, 5 hosted models, adventureworks | `adventureworks/naive-gemini-*.json` | done |
| `mcp-postgres`, car_rental | `mcp-postgres.json` | done, 79.5% |
| Excel report quality, 5 hosted models | `report-gemini-*.json` | done |
| `claude-agent`, 4 models, car_rental | `claude-agent-claude-*.json` | haiku 84.1%, sonnet 93.2%, opus 81.8% done; **fable partial, see below** |
| `codex-agent`, 3 models, car_rental | `codex-agent-gpt-*.json` | luna 86.4%, terra 90.9%, sol 95.5% -- all done |
| `local`, 5 models, car_rental | `local-{arctic-7b-q4,arctic-7b-q8,qwen35-9b,bonsai-27b-q1,qwen36-35b-moe}.json` | done, 63.6%-93.2% |
| `local`, 5 models, adventureworks | `adventureworks/local-*.json`, same five | done, 55.1%-85.7% |
| `local`, `qwen36-27b-iq3`, car_rental | `local-qwen36-27b-iq3.json` | done, 90.9% |

**Stale** -- scored against the old question set, must be re-run before being
cited next to anything above:

| file | why it is stuck |
| --- | --- |
| `pipeline.json` (80.8%) | needs `rag-service` on :8100; not running |
| `local-qwen3.5-9b.json` (69.2%) | superseded by `local-qwen35-9b.json` on the current set |
| `local-bonsai-27b-q1_0-vulkan.json` (76.9%) | superseded by `local-bonsai-27b-q1.json`; kept for the Vulkan-vs-CUDA backend note |
| `local-*-limit10.json` (2) | truncated runs, kept only for the backend note |
| `report-qwen3.5-9b.json` (15.4% chart), `report-bonsai-27b-q1_0.json` (96.2%) | needs `llama-server` on :1234; not re-run in the local sweep, which measured SQL only |
| `naive.json` | superseded by the per-model `naive-gemini-*` files |
| `repeat/naive-gemini-2.5-flash-run{3..6}.json` | the sampling-noise study, four runs of the old set |
| `variance.json` | the six-run variance study, old set |

Two of those are worth re-running for their own sake rather than just for
tidiness. The **variance study** is what established that the six-run spread on
gemini-2.5-flash was 3.8 points once the questions were unambiguous; the second
wave adds questions with genuinely harder SQL *and* six deliberately tempting
ambiguous ones, and there is no reason to assume the old spread still holds --
if it widened, some of the differences reported above are noise. The
**pipeline** arm is the project's own system and currently has no current
number at all, which is the one row a thesis cannot leave stale.

**Never measured:** Excel report quality on adventureworks (`report_score.py`
has only ever been run against car_rental); both agent arms on adventureworks --
the agent arms are car_rental-only so far, so nothing yet says whether an
agent's disadvantage grows or shrinks with schema size; Excel report quality for
any local model on the current question set (the local sweep scored SQL only);
and the two dense-27B cells discussed under *The dense-27B cost*, which were
stopped deliberately rather than left undone by accident.

### What the category grouping shows

Rendering the second wave through `tables.py`'s grouped columns isolates where
the one clearly-separated model loses. gemini-2.5-flash on car_rental:

| simple | aggregate | join | subquery | window | structure | measure | time |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 100% | 100% | 100% | 100% | 80% | **60%** | **75%** | **75%** |

Every point it drops is in the window column or in one of the three groups the
second wave added. The four original categories are still answered perfectly.
That is the cleanest evidence that the new questions are testing what they were
designed to test rather than just being longer.

---

# Agent arms: measured 2026-08-30/31, car_rental

Two arms were added for this. Both are agentic in the same sense as
`mcp-postgres` -- the model is given no schema and explores the live database
through the postgres MCP server (`list_tables`, `describe_table`, `get_schema`,
`run_query`) until it decides it knows enough -- and both are driven as
subprocesses of a coding CLI rather than through an SDK, because the
credentials live in the CLI's own session and because the thing being measured
is the agent as shipped, default system prompt and all.

- `claude-agent` -- `claude -p ... --output-format json --mcp-config ...`
- `codex-agent` -- `codex exec ... --json -c mcp_servers.postgres...`

## Results

| arm : model | correct | accuracy | asked / ambiguous | median latency | mean prompt tok | measured $/100q |
| --- | --- | --- | --- | --- | --- | --- |
| codex-agent : gpt-5.6-sol | 42/44 | **95.5%** | 4/7 | 23.6 s | 67,848 | n/a |
| claude-agent : claude-sonnet-5 | 41/44 | **93.2%** | 3/7 | 12.4 s | 162,170 | $9.44 |
| codex-agent : gpt-5.6-terra | 40/44 | **90.9%** | 6/7 | 18.0 s | 64,916 | n/a |
| codex-agent : gpt-5.6-luna | 38/44 | **86.4%** | 3/7 | 22.0 s | 70,978 | n/a |
| claude-agent : claude-haiku-4-5 | 37/44 | **84.1%** | 3/7 | 18.2 s | 100,572 | $3.33 |
| claude-agent : claude-opus-5 | 36/44 | **81.8%** | 6/7 | 18.0 s | 126,673 | $23.19 |
| claude-agent : claude-fable-5 | 33/36 | **91.7%**\* | 4/4 | 12.6 s | 110,266 | $58.27 |
| `mcp-postgres` (gemini-2.5-flash) | 35/44 | 79.5% | 1/7 | 4.8 s | -- | -- |
| `naive` (best hosted, one shot) | 44/44 | 100% | 3/7 | 2.8 s | 1,511 | $0.37 |

\* **The Fable row is a partial run and its headline 75.0% must not be cited.**
The account's usage limit was reached at q41; the CLI then exited 1 with empty
stderr in ~2 s for each of the remaining 11 questions (q41-q51, 8 scored plus 3
ambiguous). 91.7% is its accuracy over the 36 questions it actually answered,
which is not comparable with a full 44-question row. The results file carries a
`partial_run` block recording this, and the arm needs re-running. No other run
had a single infrastructure failure.

## What these numbers say

**Every agent arm loses to the one-shot baseline, and it is not close.** The
naive whole-schema arm answers 44/44; the best agent answers 42/44 and most sit
in the 80s. This is the second-wave finding from `mcp-postgres` reproducing
across seven more models and two entirely different agent harnesses, which
makes it much harder to dismiss as a quirk of one implementation. An agent that
explores has more ways to go wrong than a model shown the whole schema once:
it sees `maintenance_records` and reaches for it where the gold reads
`vehicles.status`, and each extra tool round is another chance to drift.

**Capability does not order the agent rows.** claude-opus-5 (81.8%) scores below
claude-sonnet-5 (93.2%) and below claude-haiku-4-5 (84.1%). Whatever these runs
measure, it is not raw model strength -- it is how a particular harness's
default behaviour interacts with a schema-exploration task, and the stronger
models spend their extra capability on exploring more (opus used the most tool
turns, 4.9) rather than on answering more accurately.

**The ambiguity result inverts.** On the one-shot arm every model answered all
six subtle-ambiguous questions without asking (0/5). As agents, several ask:
opus-5 and terra both handled 6/7. Giving a model tools and letting it look at
the data appears to make it *more* willing to say the question is
under-specified -- plausibly because it can see the three candidate denominators
rather than having to imagine them. That is a genuinely useful finding for the
thesis's own clarification design and deserves following up, because it is the
one dimension on which the agent arms beat the baseline.

**Cost separates the arms far more than accuracy does.** $0.37 per 100 questions
for the one-shot arm against $3.33-$58.27 for the Claude agent arm: an agent
costs 9x to 157x more and answers fewer questions correctly. The driver is
visible in the prompt-token column -- 65k-162k mean prompt tokens against the
naive arm's 1,511, because an agent re-sends its whole context every turn on top
of the CLI's own system prompt. These are the CLI's own cache-aware figures, not
list-price extrapolations, which would overstate them further.

Codex reports no cost in its JSON and `gpt-5.6-*` has no published rate card
here, so those rows have no cost column rather than an invented one.

## Caveats on this comparison

- **Harness overhead is not model overhead.** Both agent CLIs carry a large
  default system prompt the leaner arms do not. The prompt-token column is
  therefore a property of the harness, and these rows belong next to
  `mcp-postgres`, not next to `naive`.
- **Codex needed its sandbox disabled to work at all.** MCP tool calls are
  refused in headless mode unless approvals and sandbox are both bypassed
  (openai/codex#24135); the documented `default_tools_approval_mode="auto"` and
  per-server `approval_mode` keys were both tried on 0.151.0 and neither works.
  The arm runs with `--dangerously-bypass-approvals-and-sandbox` pointed at an
  empty scratch directory rather than the repository, so the unsandboxed shell
  has nothing of the project in reach and the MCP server still refuses anything
  that is not a SELECT.
- **car_rental only.** Neither agent arm has been run against adventureworks, so
  nothing here says whether the agent penalty grows or shrinks with schema size.
  That is the obvious next measurement.

## Local models: three harness faults the hosted arms never exposed

Running the local models required fixing three things in the harness first. All
three had been latent since the first wave, and each one was silently
subtracting accuracy from local models only -- which is exactly the shape of
error that produces a confident, wrong conclusion about local models being
unusable.

**1. Output-format assumptions.** `_strip_fences` stripped a fence only when the
reply *began* with one. That covers every hosted model, because they comply with
"respond with ONLY the SQL". It does not cover a reasoning-tuned local model:
Arctic-Text2SQL-R1 narrates its derivation in prose and puts the finished query
in a trailing ```sql block. The whole narration was being handed to Postgres as
the prediction, so the model scored 0/2 on questions it had in fact answered
correctly. The extractor now takes the *last* fenced block when one is present.
Both shapes the hosted arms actually produce -- bare SQL, and a single fenced
block that is the entire reply -- return byte-identical results to the previous
version, so no hosted number moves.

**2. A token budget that was scoring as incompetence.** `LOCAL_MAX_TOKENS`
defaulted to 2,048, raised to 4,096 for the first sweep. A model that reasons
before it answers spends most of its budget getting to the query. At 4,096,
Qwen3.5-9B was cut off mid-derivation on 6 of 44 car_rental questions. Those
6 were counted as wrong. Raising the budget to 8,192 -- which still fits the
largest prompt in this benchmark, AdventureWorks at 6,967 tokens, inside the
16,384-token context, so it costs no VRAM -- moved that model from 68.2% to
70.5% on car_rental and from **57.1% to 67.3% on AdventureWorks**. Ten points
of apparent inability were a cap. The first sweep was discarded and every model
re-run at 8,192 rather than patching the affected rows, so that every row in
the table below was produced under identical settings.

**3. Truncation was being counted as ambiguity handling.** The arm computed
`clarified = not sql`, on the reasoning that a naive one-shot model refusing to
emit SQL is the closest thing it has to recognising an ambiguous question. That
is defensible for a refusal. It is not defensible for a reply the server cut off
at the token limit, and it put those 6 truncated Qwen answers into the
`ambiguous_clarified` column -- flattering the one metric this thesis argues
from most directly. Truncation is now detected from `finish_reason == "length"`,
recorded separately in `extra.truncated`, and excluded from `clarified`.

Result files written before fix 3 carry no `extra.truncated` key at all, which
`benchmark/local_table.py` uses as a staleness marker: such a file is reported
as stale rather than averaged into the table.

### The dialect finding

The dominant failure mode of the SQL-specialist model is not reasoning. It is
dialect. Of Arctic-Text2SQL-R1's 10 execution errors on car_rental, 8 are
SQLite builtins that PostgreSQL does not have -- `strftime`, `julianday`,
`date(...)` used as a date constructor, and date-minus-integer arithmetic. The
model was trained on Spider and BIRD, both of which ship SQLite, and it emits
SQLite datetime functions despite a prompt that says "PostgreSQL" and a schema
rendered in PostgreSQL types.

This matters for the thesis in two directions. It means a leaderboard figure
(Arctic reports 68.5% on BIRD) does not transfer to another engine, so
"specialist model" is a claim about a dialect as much as about a task. And it
means the local-model column has a headroom figure that a single deterministic
rewriting pass would recover, which the `ceiling if dialect fixed` column in the
table reports. That column is **not an accuracy figure and must not be quoted as
one** -- it is the size of the dialect problem, measured.

### Local model results

Hardware: RTX 5070, 12 GiB VRAM; 31 GiB system RAM; i9-14900K. Backend:
llama.cpp (LM Studio's CUDA build, `cb295bf`), 16,384-token context, 8,192-token
output budget, temperature 0, served over the OpenAI-compatible endpoint. The
arm is byte-identical to `naive` in prompt and contract, so a local row and a
hosted row differ only in which model answered. Regenerate the tables with
`.venv/bin/python benchmark/local_table.py` -- every figure is read back out of
`benchmark/results/`.

`ceiling if dialect fixed` is **not an accuracy figure**: it is what the model
would reach if every failure that is purely a SQLite builtin were rewritten to
its PostgreSQL equivalent. It is reported to size the dialect problem, not to
credit the model.

### car_rental

| model | acc | correct/n | exec err | of which dialect | ceiling if dialect fixed | no SQL | trunc | tok/s | med lat |
|---|---|---|---|---|---|---|---|---|---|
| qwen36-35b-moe | 93.2% | 41/44 | 2 | 0 | 93.2% | 3 | 0 | 50 | 39.5s |
| qwen36-27b-iq3 | 90.9% | 40/44 | 3 | 0 | 90.9% | 1 | 0 | 8 | 268.5s |
| qwen35-9b | 70.5% | 31/44 | 0 | 0 | 70.5% | 7 | 5 | 92 | 8.7s |
| arctic-7b-q4 | 65.9% | 29/44 | 10 | 8 | 84.1% | 1 | 0 | 112 | 4.0s |
| arctic-7b-q8 | 63.6% | 28/44 | 9 | 6 | 77.3% | 3 | 0 | 71 | 6.1s |
| bonsai-27b-q1 | 63.6% | 28/44 | 6 | 0 | 63.6% | 8 | 7 | 53 | 47.2s |

Not run: `qwen36-27b-q4` -- see *The dense-27B cost* below.

### adventureworks

| model | acc | correct/n | exec err | of which dialect | ceiling if dialect fixed | no SQL | trunc | tok/s | med lat |
|---|---|---|---|---|---|---|---|---|---|
| qwen36-35b-moe | 85.7% | 42/49 | 1 | 0 | 85.7% | 1 | 0 | 49 | 45.9s |
| bonsai-27b-q1 | 69.4% | 34/49 | 7 | 0 | 69.4% | 3 | 3 | 51 | 50.9s |
| qwen35-9b | 67.3% | 33/49 | 4 | 0 | 67.3% | 1 | 1 | 88 | 6.9s |
| arctic-7b-q4 | 55.1% | 27/49 | 11 | 7 | 69.4% | 2 | 0 | 103 | 3.5s |
| arctic-7b-q8 | 55.1% | 27/49 | 14 | 7 | 69.4% | 2 | 1 | 66 | 5.2s |

Not run: `qwen36-27b-iq3`, `qwen36-27b-q4` -- see *The dense-27B cost* below.

### What the local rows say

**A 35B MoE on a 12 GiB consumer card matches the best cloud agent arm.**
Qwen3.6-35B-A3B at Q4, with 28 layers' worth of experts held in system RAM
(`--n-cpu-moe 28`), scores 93.2% on car_rental -- the same as `claude-agent`
driving Sonnet 5 (41/44), and above every other agent arm measured, including
Opus 5 at 81.8%. On AdventureWorks it scores 85.7%, which no agent arm has been
run against for comparison. It sustains ~47 tokens/s in that configuration.
This is the single most consequential local result: the sparse-activation
architecture is what makes it possible, because only ~3B parameters are active
per token, so the PCIe round trip to the CPU-resident experts is paid on a small
fraction of the weights.

**The MoE is the only local model that clears the second wave.** Every dense
local model lands between 55% and 71%, and the gap to the MoE is 23 points --
far larger than any gap between the dense models themselves. The hard questions
added in the second wave separate local models from each other much more
cleanly than they separate the hosted models, three of which are still at 100%.

**Quantisation is not where the accuracy went.** The only clean quantisation
comparison in this table is Arctic-Text2SQL-R1, where the *same weights* are
measured twice: Q8_0 (8.10 GiB) scores *below* Q4_K_M (4.68 GiB) on car_rental
(63.6% vs 65.9%) and identically on AdventureWorks (55.1% both), while running
at 60% of the speed. Doubling the bits bought nothing here.

Bonsai-27B at Q1_0 -- 1.125 bits per weight, a 3.80 GiB file -- scores 63.6%
and 69.4%, beating both Arctic quants on AdventureWorks. It is worth being
precise about what that does and does not show. Bonsai shares Qwen3.6-27B's
architecture exactly (`qwen35`, 64 blocks, 27B) but its GGUF `general.basename`
is `prism-ml_Bonsai` and it declares no `base_model` link, whereas the Qwen3.6
files declare `Qwen/Qwen3.6-27B`. It is a *different model*, not a one-eighth
compression of the one two rows below it, and the 27-point gap between it and
Qwen3.6-27B-IQ3_XXS is therefore a model difference with a quantisation
difference folded into it, not a measurement of what 1-bit quantisation costs.
An earlier version of this file and of `serve_local.sh` asserted otherwise; the
GGUF metadata says no.

**Verbosity is a real cost for the small models.** Even at an 8,192-token
budget, Bonsai-27B was still cut off on 7 of 44 car_rental questions and 3 of
49 AdventureWorks questions, and Qwen3.5-9B on 5 and 1. Those are counted as
failures in the table above, which is the honest treatment -- a query the system
never finishes emitting is a query the user does not get -- but it means part of
the dense models' deficit is output discipline rather than SQL knowledge.

### The dense-27B cost, and why the MoE is the finding

Two cells in the tables above are empty on purpose, and the reason is the
result rather than an omission from it.

Qwen3.6-27B is a *dense* model. Every one of its 27 billion parameters is read
for every token generated. At Q4_K_M the file is 16.0 GiB against ~11.1 GiB of
usable VRAM, so roughly 5 GiB of weights live in system RAM and cross the bus on
every single token: **4.0 tokens/s**. At IQ3_XXS the file is 12.0 GiB, the spill
is smaller, and it manages **8.2 tokens/s** -- still slow enough that a single
second-wave question with a long derivation takes seventeen minutes, and the
44-question car_rental set took just under four hours.

Qwen3.6-35B-A3B is a *sparse* model. Its file is **larger** (21.1 GiB, so
*more* of it is in system RAM) and it runs at **47 tokens/s** -- twelve times
faster than the dense 27B -- because only ~3B of its 35B parameters are active
for any given token, so the RAM-resident experts are mostly not touched. Held
there deliberately with `--n-cpu-moe 28`.

That inversion is the practical finding of this whole section. On a 12 GiB
consumer card the binding constraint is not how large the model file is; it is
how much of the model each token has to read. A 35B sparse model is both more
accurate (93.2% vs 90.9%) and an order of magnitude faster than a 27B dense one
that is a third smaller on disk. For a system that has to answer a user in
interactive time, the dense 27B rows are not a viable configuration on this
hardware at any accuracy, and that is what their tokens/s column is there to
say.

Given that, `qwen36-27b-q4` was stopped after 16 of 44 car_rental questions and
`qwen36-27b-iq3` was not run against adventureworks. Between them those two
cells were about nine hours of wall clock for one point on a quantisation
ladder whose neighbouring rungs -- Arctic Q4_K_M vs Q8_0, at 65.9% and 63.6% --
show a spread of about two points. `run.py` writes its result file only on
completion, so neither leaves a partial file behind; `benchmark/local_table.py`
prints them as not run.

### Where this leaves the local-versus-hosted comparison

The best local model now sits inside the band the hosted models occupy on this
benchmark rather than below it. On car_rental, `qwen36-35b-moe` at 93.2% is
level with the best agent arm measured (`claude-agent` on Sonnet 5, 41/44) and
above every other agentic row: `codex-agent` on Terra (90.9%) and Luna (86.4%),
`claude-agent` on Haiku 4.5 (84.1%) and Opus 5 (81.8%), and `mcp-postgres`
(79.5%). It also clears the weakest hosted one-shot row, `gemini-2.5-flash` at
88.6%. What it does not clear is the top of the naive arm, where three of the
five hosted models are still at 100% -- so the ceiling this benchmark was
rebuilt to break is still standing for the strongest hosted models, and the
local result is a statement about the middle of the field, not the top of it.

What it costs to get there is the honest counterweight. The hosted naive arm
answers in a median 2.8 seconds for $0.37 per hundred questions; the local MoE
takes a median 39.5 seconds and no per-token fee, on hardware already bought.
The thesis claim this supports is narrow and defensible: on a schema of this
size, a locally served sparse model reaches accuracy competitive with hosted
agentic systems, at roughly an order of magnitude more latency and no
marginal cost -- which is the trade that matters when the data cannot leave the
building.
