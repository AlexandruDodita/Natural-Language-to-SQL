# Benchmark results

**Text-to-SQL — 18 systems over 2 PostgreSQL databases (93 scored questions), plus 4 runs over BIRD-SQL dev (1,534 questions, 11 SQLite databases).**
Measured 2026-08-30 / 2026-08-31. Every figure in this document is read back out
of `benchmark/results/*.json` by `benchmark/tables.py` and
`benchmark/local_table.py`; nothing here is transcribed by hand.

---

## 1. What was measured

| | |
| --- | --- |
| **Task** | Natural-language question → one PostgreSQL query, executed against the live database |
| **Metric** | **Execution accuracy** — the predicted query's result set is compared against the gold query's result set. Not string similarity. |
| **Databases** | `car_rental` — 9 tables, ~70 columns, 8,026 rows, schema ~1k tokens. `adventureworks` — Microsoft's sample OLTP database, 68 tables, 1,099 columns, 91 FKs, ~761k rows across five schemas, schema ~9k tokens. `bird_dev` — BIRD-SQL dev, 11 SQLite databases, question revision 2026-11-06 (§10) |
| **Questions** | `car_rental`: 51 total → **44 scored** + 7 ambiguous. `adventureworks`: 56 total → **49 scored** + 7 ambiguous |
| **Ambiguous questions** | Scored separately, on whether the system *asked a clarifying question* instead of guessing |
| **Question-set identity** | Fingerprinted (`86e194123bb3` car_rental, `5398f281a907` adventureworks) so a result file scored against a superseded wording is flagged automatically, not silently averaged in |

> **Who wrote the questions.** `car_rental` and `adventureworks` are hand-written
> for this thesis — AdventureWorks ships a database, not a question set, and no
> standard text-to-SQL benchmark uses it. So every number in §2–§8 is a system
> measured against questions its own author wrote, which is a validity limit
> worth naming rather than burying. **§10 is the answer to it**: BIRD-SQL is
> externally authored, with published gold SQL, a published metric and a public
> leaderboard.

### The three arms

| arm | what the model is given | who runs the loop |
| --- | --- | --- |
| **`naive`** | The entire schema as text, one API call, "return only the SQL" | nobody — single shot |
| **`agentic`** | No schema. The model explores the live DB through the Postgres MCP server (`list_tables`, `describe_table`, `run_query`) until it decides it knows enough | a coding CLI (`claude -p`, `codex exec`) or the project's own MCP arm |
| **`local`** | Identical prompt and contract to `naive` — the *only* difference is which model answers | nobody — single shot, served by llama.cpp on the local GPU |

The local arm being byte-identical to `naive` is deliberate: a local row and a
hosted row differ in one variable only.

---

## 2. Headline — every system, `car_rental` (44 scored)

| # | system | arm | correct | accuracy |
| --- | --- | --- | --- | --- |
| 1 | gemini-3.1-pro-preview | naive | 44/44 | **100.0%** |
| 1 | gemini-3.6-flash | naive | 44/44 | **100.0%** |
| 1 | gemini-3.7-flash | naive | 44/44 | **100.0%** |
| 4 | gemini-3-flash-preview | naive | 43/44 | 97.7% |
| 5 | codex-agent : gpt-5.6-sol | agentic | 42/44 | 95.5% |
| 6 | **qwen3.6-35B-A3B (local, Q4)** | **local** | **41/44** | **93.2%** |
| 6 | claude-agent : claude-sonnet-5 | agentic | 41/44 | 93.2% |
| 8 | codex-agent : gpt-5.6-terra | agentic | 40/44 | 90.9% |
| 8 | **qwen3.6-27B (local, IQ3\_XXS)** | **local** | **40/44** | **90.9%** |
| 10 | gemini-2.5-flash | naive | 39/44 | 88.6% |
| 11 | codex-agent : gpt-5.6-luna | agentic | 38/44 | 86.4% |
| 12 | claude-agent : claude-haiku-4-5 | agentic | 37/44 | 84.1% |
| 13 | claude-agent : claude-opus-5 | agentic | 36/44 | 81.8% |
| 14 | mcp-postgres (gemini-2.5-flash) | agentic | 35/44 | 79.5% |
| 15 | qwen3.5-9B (local, Q4) | local | 31/44 | 70.5% |
| 16 | Arctic-Text2SQL-R1-7B (local, Q4) | local | 29/44 | 65.9% |
| 17 | Arctic-Text2SQL-R1-7B (local, Q8) | local | 28/44 | 63.6% |
| 17 | Bonsai-27B (local, Q1) | local | 28/44 | 63.6% |

`claude-agent : claude-fable-5` is excluded — its run was cut short by an
account usage limit at q41 (see §9).

### Same picture on `adventureworks` (49 scored)

| # | system | arm | correct | accuracy |
| --- | --- | --- | --- | --- |
| 1 | gemini-3.1-pro-preview | naive | 49/49 | **100.0%** |
| 1 | gemini-3.7-flash | naive | 49/49 | **100.0%** |
| 3 | gemini-3-flash-preview | naive | 48/49 | 98.0% |
| 3 | gemini-3.6-flash | naive | 48/49 | 98.0% |
| 5 | gemini-2.5-flash | naive | 45/49 | 91.8% |
| 6 | **qwen3.6-35B-A3B (local, Q4)** | **local** | **42/49** | **85.7%** |
| 7 | Bonsai-27B (local, Q1) | local | 34/49 | 69.4% |
| 8 | qwen3.5-9B (local, Q4) | local | 33/49 | 67.3% |
| 9 | Arctic-Text2SQL-R1-7B (local, Q4) | local | 27/49 | 55.1% |
| 9 | Arctic-Text2SQL-R1-7B (local, Q8) | local | 27/49 | 55.1% |

No agent arm has been run against `adventureworks` yet.

### The three results worth defending

1. **A 35B sparse model on a 12 GiB consumer GPU matches the best cloud agent.**
   93.2% — identical to `claude-agent` on Sonnet 5, above Opus 5 (81.8%), Terra
   (90.9%) and every other agentic row. No data leaves the machine, no
   per-token cost.
2. **Every agentic system loses to the naive one-shot baseline, and it isn't
   close.** Best agent 95.5% vs. three naive rows at 100%. Giving the model
   tools and letting it explore the database makes it *worse* at writing the
   query. This reproduces across two entirely different agent CLIs plus this
   project's own MCP arm, over seven models, so it is not a quirk of one
   implementation.
3. **Ambiguity, not SQL difficulty, is where the real capability gap is.**
   Every one-shot model answered *every* subtly-ambiguous question without
   asking — 0/5, on both databases, unanimously (§7).

---

## 3. Arm A — `naive` (hosted, one shot)

| model | car_rental | AdventureWorks | median latency | prompt tok | output tok | $/100 questions |
| --- | --- | --- | --- | --- | --- | --- |
| gemini-3.7-flash | **100.0%** (44/44) | **100.0%** (49/49) | 2.7 s | 1,511 | 685 | $0.37 |
| gemini-3.1-pro-preview | **100.0%** (44/44) | **100.0%** (49/49) | 6.7 s | 1,511 | 1,470 | $2.07 |
| gemini-3.6-flash | **100.0%** (44/44) | 98.0% (48/49) | 6.4 s | 1,511 | 1,079 | $0.52 |
| gemini-3-flash-preview | 97.7% (43/44) | 98.0% (48/49) | 4.4 s | 1,511 | 1,547 | $0.54 |
| gemini-2.5-flash | 88.6% (39/44) | 91.8% (45/49) | 1.9 s | 1,511 | 654 | $0.21 |

Costs are list-price extrapolations from measured token counts (prices checked
2026-08-23).

**Reading it.** The current question set separates `gemini-2.5-flash`
decisively and nicks the two flash-preview models, but three of five hosted
models still answer everything. The generation gap is real and large:
2.5-flash → 3.7-flash is +11.4 points on `car_rental` at a comparable price.

---

## 4. Arm B — agentic (`car_rental` only)

| arm : model | correct | accuracy | tool turns (mean) | median latency | mean prompt tok | measured $/100q |
| --- | --- | --- | --- | --- | --- | --- |
| codex-agent : gpt-5.6-sol | 42/44 | **95.5%** | 2.2 | 23.6 s | 67,848 | not reported |
| claude-agent : claude-sonnet-5 | 41/44 | **93.2%** | 4.4 | 12.4 s | 162,170 | $9.44 |
| codex-agent : gpt-5.6-terra | 40/44 | **90.9%** | 2.0 | 18.0 s | 64,916 | not reported |
| codex-agent : gpt-5.6-luna | 38/44 | 86.4% | 2.5 | 22.0 s | 70,978 | not reported |
| claude-agent : claude-haiku-4-5 | 37/44 | 84.1% | 4.1 | 18.2 s | 100,572 | $3.33 |
| claude-agent : claude-opus-5 | 36/44 | 81.8% | 4.9 | 18.0 s | 126,673 | $23.19 |
| mcp-postgres (gemini-2.5-flash) | 35/44 | 79.5% | 2.4 | 4.8 s | — | — |
| *(reference)* naive, best hosted | 44/44 | 100.0% | 0 | 2.7 s | 1,511 | $0.37 |

Claude costs are the CLI's own cache-aware figures, not list-price
extrapolations — list price would put Sonnet at $33.35 and Opus at $66.49.

**Reading it.**

- **Capability does not order these rows.** Opus 5 (81.8%) sits below Sonnet 5
  (93.2%) *and* below Haiku 4.5 (84.1%). The stronger models spend their extra
  capability on exploring more — Opus used the most tool turns, 4.9 — rather
  than on answering more accurately. What this arm measures is how a harness's
  default behaviour interacts with a schema-exploration task, not raw model
  strength.
- **Cost separates the arms far more than accuracy does.** $0.37 per 100
  questions one-shot against $3.33–$23.19 agentic: **9× to 63× more expensive,
  for fewer correct answers.** The driver is the prompt-token column — 65k–162k
  mean prompt tokens against 1,511, because an agent re-sends its whole context
  every turn on top of the CLI's own system prompt.
- **Caveat:** that prompt-token overhead is a property of the *harness*, not the
  model. These rows belong next to `mcp-postgres`, not next to `naive`.

---

## 5. Arm C — local models (llama.cpp, RTX 5070)

Hardware: **RTX 5070, 12 GiB VRAM; 31 GiB system RAM; i9-14900K.** Backend:
llama.cpp (LM Studio CUDA build `cb295bf`), 16,384-token context, 8,192-token
output budget, temperature 0, served over the OpenAI-compatible endpoint.

### 5a. Accuracy

**`car_rental` (44 scored)**

| model | accuracy | correct | exec err | of which dialect | ceiling if dialect fixed | no SQL | truncated |
| --- | --- | --- | --- | --- | --- | --- | --- |
| qwen3.6-35B-A3B Q4 (MoE) | **93.2%** | 41/44 | 2 | 0 | 93.2% | 3 | 0 |
| qwen3.6-27B IQ3_XXS | **90.9%** | 40/44 | 3 | 0 | 90.9% | 1 | 0 |
| qwen3.5-9B Q4 | 70.5% | 31/44 | 0 | 0 | 70.5% | 7 | 5 |
| Arctic-Text2SQL-R1-7B Q4 | 65.9% | 29/44 | 10 | **8** | *84.1%* | 1 | 0 |
| Arctic-Text2SQL-R1-7B Q8 | 63.6% | 28/44 | 9 | **6** | *77.3%* | 3 | 0 |
| Bonsai-27B Q1 | 63.6% | 28/44 | 6 | 0 | 63.6% | 8 | 7 |

**`adventureworks` (49 scored)**

| model | accuracy | correct | exec err | of which dialect | ceiling if dialect fixed | no SQL | truncated |
| --- | --- | --- | --- | --- | --- | --- | --- |
| qwen3.6-35B-A3B Q4 (MoE) | **85.7%** | 42/49 | 1 | 0 | 85.7% | 1 | 0 |
| Bonsai-27B Q1 | 69.4% | 34/49 | 7 | 0 | 69.4% | 3 | 3 |
| qwen3.5-9B Q4 | 67.3% | 33/49 | 4 | 0 | 67.3% | 1 | 1 |
| Arctic-Text2SQL-R1-7B Q4 | 55.1% | 27/49 | 11 | **7** | *69.4%* | 2 | 0 |
| Arctic-Text2SQL-R1-7B Q8 | 55.1% | 27/49 | 14 | **7** | *69.4%* | 2 | 1 |

> *`ceiling if dialect fixed` is **not an accuracy figure and must not be quoted
> as one.*** It is what the model would reach if every failure that is purely a
> SQLite builtin were mechanically rewritten to its PostgreSQL equivalent. It is
> reported to **size the dialect problem**, not to credit the model.

### 5b. Throughput and the offload split

| model | file | VRAM at load | how it fits | decode tok/s | median latency | wall clock, 44 q |
| --- | --- | --- | --- | --- | --- | --- |
| Arctic-7B Q4 | 4.4 GiB | 6,055 MiB | fully resident | 113 | 4.0 s | 4 min |
| Arctic-7B Q8 | 7.5 GiB | 9,067 MiB | fully resident | 72 | 6.1 s | 5 min |
| qwen3.5-9B Q4 | 5.2 GiB | 6,702 MiB | fully resident | 91 | 8.7 s | 15 min |
| Bonsai-27B Q1 | 3.5 GiB | 6,284 MiB | fully resident | 53 | 47.2 s | 50 min |
| **qwen3.6-35B-A3B Q4** | **20.6 GiB** | 9,620 MiB | **experts → RAM** (`--n-cpu-moe 28`) | **50** | 39.5 s | **37 min** |
| qwen3.6-27B IQ3_XXS | 11.2 GiB | 10,438 MiB | partial layer offload | **8** | 268.5 s | **247 min** |
| qwen3.6-27B Q4_K_M | 15.7 GiB | 10,410 MiB | partial layer offload | **4** | — | *stopped at 16/44* |

### 5c. The finding: density, not file size, is the binding constraint

Read the last three rows together.

| | qwen3.6-**27B** Q4 (dense) | qwen3.6-**27B** IQ3 (dense) | qwen3.6-**35B**-A3B Q4 (sparse) |
| --- | --- | --- | --- |
| file size | 15.7 GiB | 11.2 GiB | **20.6 GiB — the largest** |
| params read per token | all 27 B | all 27 B | **~3 B of 35 B** |
| decode speed | 4 tok/s | 8 tok/s | **50 tok/s** |
| accuracy (car_rental) | — | 90.9% | **93.2%** |

The **largest file in that group is 12× faster** than the dense model a third
smaller on disk, and more accurate than either dense row.
On a 12 GiB card the constraint is not how big the model is, it is **how much of
it every token has to read**. A dense 27B spills ~5 GiB across the PCIe bus on
*every token*; a sparse 35B keeps its experts in system RAM and mostly doesn't
touch them. For an interactive system the dense 27B rows are not a viable
configuration on this hardware **at any accuracy**, and that is what their
tok/s column exists to say.

Two cells were therefore stopped deliberately: `qwen36-27b-q4` (both datasets,
after 16 of 44 questions) and `qwen36-27b-iq3` on `adventureworks`. Between them
they were ~9 hours of wall clock for one rung of a quantisation ladder whose
neighbouring rungs differ by two points.

### 5d. Two secondary local findings

**Quantisation is not where the accuracy went.** Arctic-Text2SQL-R1 is measured
twice at the *same weights*: Q8_0 (7.5 GiB) scores **below** Q4_K_M (4.4 GiB) on
car_rental — 63.6% vs 65.9% — and identically on AdventureWorks (55.1% both),
while running at 64% of the speed. Doubling the bits bought nothing.

**The SQL specialist's problem is dialect, not reasoning.** Of Arctic's 10
execution errors on car_rental, **8 are SQLite builtins PostgreSQL does not
have** — `strftime`, `julianday`, `date(...)` as a constructor, date-minus-integer
arithmetic. It was trained on Spider and BIRD, both of which ship SQLite, and it
emits SQLite datetime functions despite a prompt that says "PostgreSQL" and a
schema rendered in PostgreSQL types. **A leaderboard figure does not transfer
across engines**: "specialist model" is a claim about a dialect as much as about
a task.

---

## 6. Where the difficulty actually is — accuracy by question type

Question counts per group — car_rental: simple 6, aggregate 9, join 5, subquery
6, window 5, structure 5, measure 4, time 4. `structure` = multi-level
aggregation, self-join, anti-join, recursive, set ops, gaps-and-islands;
`measure` = ratio, percentile, pivot; `time` = temporal, calendar, cohort.

**`car_rental`**

| system | simple | aggregate | join | subquery | window | structure | measure | time | total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| naive: gemini-3.7-flash | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | **100.0%** |
| naive: gemini-3.6-flash | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | **100.0%** |
| naive: gemini-3.1-pro | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | **100.0%** |
| naive: gemini-3-flash-prev | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 75% | **97.7%** |
| codex-agent: sol | 100% | 100% | 80% | 100% | 80% | 100% | 100% | 100% | **95.5%** |
| local: qwen3.6-35B-MoE | 100% | 100% | 100% | 83% | 100% | 100% | 75% | 75% | **93.2%** |
| claude-agent: sonnet-5 | 100% | 89% | 80% | 83% | 100% | 100% | 100% | 100% | **93.2%** |
| local: qwen3.6-27B-IQ3 | 100% | 100% | 100% | 100% | 80% | 80% | 75% | 75% | **90.9%** |
| codex-agent: terra | 100% | 89% | 80% | 83% | 100% | 80% | 100% | 100% | **90.9%** |
| naive: gemini-2.5-flash | 100% | 100% | 100% | 100% | 80% | **60%** | **75%** | **75%** | **88.6%** |
| codex-agent: luna | 100% | 89% | 60% | 67% | 80% | 100% | 100% | 100% | **86.4%** |
| claude-agent: haiku-4-5 | 83% | 89% | 100% | 67% | 60% | 80% | 100% | 100% | **84.1%** |
| claude-agent: opus-5 | 100% | **56%** | 100% | 67% | 100% | 100% | 75% | 75% | **81.8%** |
| mcp-postgres | 83% | 100% | 100% | 83% | 80% | **40%** | 75% | **50%** | **79.5%** |
| local: qwen3.5-9B | 100% | 89% | 80% | 50% | 60% | **40%** | 100% | **25%** | **70.5%** |
| local: Arctic-7B Q4 | 100% | 100% | 80% | 83% | **40%** | **20%** | 50% | **0%** | **65.9%** |
| local: Arctic-7B Q8 | 100% | 89% | 100% | 83% | **20%** | **0%** | 50% | 25% | **63.6%** |
| local: Bonsai-27B Q1 | 83% | 89% | 60% | 83% | 60% | **20%** | 75% | **0%** | **63.6%** |

**`adventureworks`** — counts: simple 5, aggregate 8, join 10, subquery 7,
window 5, structure 7, measure 3, time 4.

| system | simple | aggregate | join | subquery | window | structure | measure | time | total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| naive: gemini-3.1-pro | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | **100.0%** |
| naive: gemini-3.7-flash | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | **100.0%** |
| naive: gemini-3-flash-prev | 100% | 100% | 100% | 86% | 100% | 100% | 100% | 100% | **98.0%** |
| naive: gemini-3.6-flash | 100% | 100% | 100% | 100% | 80% | 100% | 100% | 100% | **98.0%** |
| naive: gemini-2.5-flash | 100% | 100% | 100% | 100% | **60%** | 100% | 67% | 75% | **91.8%** |
| local: qwen3.6-35B-MoE | 100% | 100% | 90% | 86% | **60%** | 100% | 67% | **50%** | **85.7%** |
| local: Bonsai-27B Q1 | 100% | 100% | 60% | 71% | **20%** | 71% | 67% | 50% | **69.4%** |
| local: qwen3.5-9B | 100% | 100% | 60% | 71% | **40%** | 43% | 67% | 50% | **67.3%** |
| local: Arctic-7B Q4 | 80% | 75% | 60% | 57% | **20%** | 43% | 67% | **25%** | **55.1%** |
| local: Arctic-7B Q8 | 80% | 75% | 50% | 71% | **20%** | 43% | 33% | 50% | **55.1%** |

**Reading it.** Every point `gemini-2.5-flash` drops on car_rental is in
`window` or in one of the three groups added in the second wave — the four
original categories are still answered perfectly. That is the cleanest evidence
that the new questions test what they were designed to test rather than just
being longer. The same columns are where the local models collapse: **`window`
and `time` are the discriminators**, and `simple`/`aggregate` discriminate
nothing at all any more.

The three recurring failure modes, inspected by hand across all runs:

| failure | what happens |
| --- | --- |
| **window frame semantics** | filtering to the reporting year *before* the window truncates the frame |
| **dialect misuse** | `round(double precision, integer) does not exist` — the two-arg `round` needs `numeric` in PostgreSQL. This is Spider 2.0's second-largest error sub-class (10.3%) reproducing exactly |
| **cohort anchoring** | anchoring a cohort to the wrong event date — Spider 2.0's flagship failure case |

---

## 7. Ambiguity — the real capability gap

Seven questions per database have no single correct answer. They are scored on
whether the system **asked** instead of guessing. Cells show *how many runs in
that family asked*.

**`car_rental`** — 5 naive runs, 8 agentic runs, 6 local runs.

| question | naive | agentic | local |
| --- | --- | --- | --- |
| q30 "Hello, what can you do?" | **5/5** | 5/8 | **6/6** |
| q28 "Show me the good vehicles." | 4/5 | **7/8** | 2/6 |
| q29 "How is the business doing?" | 3/5 | 5/8 | 1/6 |
| q27 "Care sunt cei mai buni clienți?" *(ro)* | 1/5 | 5/8 | 1/6 |
| **q49** "Care sucursală a adus cei mai mulți bani în 2024?" | **0/5** | 3/8 | 1/6 |
| **q51** "How many cars were rented last month?" | **0/5** | 3/8 | 0/6 |
| **q50** "What is our average revenue per client?" | **0/5** | 2/8 | 0/6 |

**`adventureworks`** — 5 naive runs, 5 local runs, no agentic runs yet.

| question | naive | local |
| --- | --- | --- |
| q28 "Care sunt cele mai bune produse?" *(ro)* | 2/5 | 3/5 |
| q27 "Show me our best customers." | 1/5 | 0/5 |
| q29 "How many customers do we have?" | **0/5** | 0/5 |
| q30 "What were our sales last year?" | **0/5** | 0/5 |
| **q54** "What was our average discount in 2013?" | **0/5** | 0/5 |
| **q55** "Cine este cel mai bun agent de vânzări?" | **0/5** | 2/5 |
| **q56** "How much inventory are we holding?" | **0/5** | 0/5 |

**Reading it — three things, and this is the most important section.**

1. **Ambiguity that announces itself is caught; ambiguity that hides is not.**
   A question with no metric in it at all ("How is the business doing?") gets
   asked about. A question that *looks* answerable does not. "What is our
   average revenue per client?" has three defensible denominators in this
   schema, and **every one-shot model silently picked one.**
2. **This is a capability gap, not a difficulty knob.** The models are not
   failing to write the SQL — they are failing to notice that the question does
   not determine which SQL to write. Unlike the accuracy table, this is *not*
   saturating.
3. **Tools invert the result.** As agents, several models *do* ask — Opus 5 and
   Terra both handled 6/7. Being able to *see* the three candidate denominators
   appears to make a model more willing to say the question is under-specified.
   **This is the one dimension on which the agentic arm beats the baseline**,
   and it directly supports the clarification design in this project's own
   system.

> **Method caveat:** `run.py` scores this binary. A model that answers *with an
> explicitly stated assumption* is scored identically to one that answers
> silently. Before this becomes a headline number, that should become a third
> outcome.

---

## 8. Excel report quality (`car_rental`)

Given a result set, pick the right chart type and emit a structurally valid
report spec.

| model | chart type correct | chart accuracy | chartable qs | scalar qs | structural validity | unparseable |
| --- | --- | --- | --- | --- | --- | --- |
| gemini-3.7-flash | 44/44 | **100.0%** | 100.0% | 100.0% | 100.0% | 0 |
| gemini-3.6-flash | 44/44 | **100.0%** | 100.0% | 100.0% | 100.0% | 0 |
| gemini-3-flash-preview | 44/44 | **100.0%** | 100.0% | 100.0% | 100.0% | 0 |
| gemini-2.5-flash | 44/44 | **100.0%** | 100.0% | 100.0% | 100.0% | 0 |
| gemini-3.1-pro-preview | 43/44 | 97.7% | 96.4% | 100.0% | 100.0% | 0 |

Harder SQL did not make chart selection harder — expected, because the chart
follows from the *shape* of the result set, and the second wave did not change
result shapes much. **This part of the pipeline is saturated and is not where
further work belongs.**

---

## 9. Validity — what had to be fixed, and what is still open

### Three harness faults found while running the local models

All three were latent since the first wave, and **each was silently subtracting
accuracy from local models only** — the shape of error that produces a
confident, wrong conclusion.

| # | fault | effect | fix |
| --- | --- | --- | --- |
| 1 | **Output-format assumption.** The SQL extractor stripped a code fence only when the reply *began* with one. Arctic narrates its derivation and puts the query in a *trailing* block, so the whole narration was executed as the prediction | Arctic scored **0/2 on questions it had answered correctly** | take the *last* fenced block. Both shapes hosted models produce return byte-identical results, so no hosted number moves |
| 2 | **Token budget scoring as incompetence.** `LOCAL_MAX_TOKENS` was 4,096; a model that reasons before answering spends most of that getting to the query | qwen3.5-9B cut off on 6 of 44; raising to 8,192 moved it **68.2% → 70.5%** (car_rental) and **57.1% → 67.3%** (AdventureWorks) | 8,192 — still fits the largest prompt here (6,967 tok) inside the 16,384 context, so it costs no VRAM. **The entire sweep was re-run rather than patching affected rows**, so every local row above was produced under identical settings |
| 3 | **Truncation counted as ambiguity handling.** The arm computed `clarified = not sql`, which put 6 cut-off answers into the `ambiguous_clarified` column | inflated the *one metric this thesis argues from most directly* | detect `finish_reason == "length"`, record separately in `extra.truncated`, exclude from `clarified` |

Result files written before fix 3 carry no `extra.truncated` key, which
`local_table.py` uses as a staleness marker — such a file is reported as stale
rather than quietly averaged in.

### One partial run, excluded

`claude-agent : claude-fable-5` hit the account usage limit at q41; the CLI then
exited 1 with empty stderr in ~2 s for each of the remaining 11 questions. Its
file's headline 75.0% counts 8 infrastructure failures as wrong answers and
**must not be cited**; its accuracy over the 36 questions it actually answered
was 91.7%, which is not comparable with a full 44-question row. The results file
carries a `partial_run` block recording this. **No other run had a single
infrastructure failure.**

### Coverage — what is measured and what is not

| cell | status |
| --- | --- |
| `naive`, 5 hosted models × 2 databases | ✅ done |
| `mcp-postgres`, car_rental | ✅ done (79.5%) |
| `claude-agent`, 3 models, car_rental | ✅ done (haiku / sonnet / opus) |
| `codex-agent`, 3 models, car_rental | ✅ done (luna / terra / sol) |
| `local`, 6 models, car_rental | ✅ done (63.6%–93.2%) |
| `local`, 5 models, adventureworks | ✅ done (55.1%–85.7%) |
| Excel report quality, 5 hosted models, car_rental | ✅ done |
| `naive`, 3 hosted models, BIRD-SQL dev (1,534 q) | ✅ done (55.7%–63.6%) |
| `naive`, `gemini-3.7-flash`, BIRD + data dictionary | ✅ done (64.9%) |
| local models on BIRD | ❌ not run — the MoE at ~44 s/question is ~19 h for one row |
| agent arms on BIRD | ❌ not run |
| `claude-agent : claude-fable-5` | ⚠️ partial — re-run needed |
| `qwen36-27b-q4` (both DBs), `qwen36-27b-iq3` (AW) | ⏹️ **stopped deliberately** — see §5c |
| `pipeline` arm (this project's own system) | ❌ **stale** — needs `rag-service` on :8100. *This is the one row a thesis cannot leave stale.* |
| variance / repeat-run study | ❌ stale — established a 3.8-point six-run spread on the *old* question set. The new set adds harder SQL and six tempting ambiguous questions; there is no reason to assume that spread still holds, and if it widened, some differences above are noise |
| both agent arms on adventureworks | ❌ never run — nothing yet says whether the agent penalty grows or shrinks with schema size |
| Excel report quality on adventureworks; on any local model | ❌ never run |

### Known limits of the fixture

- Two hand-written question sets, both authored by the system's own author; see
  the note in §1 and the external check in §10.
- Three databases at 9, 68 and (BIRD) 3–13 tables. Nothing here speaks to a
  300-table warehouse.
- Result-set comparison accepts a query that is right for the wrong reason.
- Ambiguity is scored binary (see §7 caveat).
- Single run per cell except where noted — differences under ~4 points on 44
  questions should be treated as within noise until the variance study is
  re-run.

---

## 10. BIRD-SQL dev — the external benchmark

Everything above measures this system against questions written by its own
author. This section does not. [BIRD-SQL](https://bird-bench.github.io/) is the
standard grounded text-to-SQL benchmark: **1,534 questions over 11 SQLite
databases**, published gold SQL, a published metric, a public leaderboard.
Question revision **2026-11-06** (`birdsql/bird_sql_dev_20251106`), paired with
the upstream database bundle.

The arm is the same `naive` arm as §3 — whole schema, one call, no retrieval,
no repair. Only the database and the dialect change.

### 10a. Results

| run | acc | correct | simple (860) | moderate (443) | challenging (231) | invalid | no SQL | med lat | cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gemini-3.7-flash **+ dictionary** | **64.9%** | 996/1534 | 74.1% | 63.2% | 34.2% | 10 | 7 | 3.1 s | $7.31 |
| gemini-3.7-flash | **63.6%** | 976/1534 | 73.3% | 61.6% | 31.6% | 12 | 8 | 3.6 s | $5.64 |
| gemini-3.1-pro-preview | **62.1%** | 952/1534 | 71.3% | 59.4% | 32.9% | 1 | 21 | 10.5 s | $29.10 |
| gemini-2.5-flash | **55.7%** | 855/1534 | 64.9% | 52.6% | 27.7% | 8 | 12 | 1.4 s | $2.76 |

Total spend $44.81. All four runs completed; no infrastructure failures.

### 10b. BIRD un-saturates the benchmark

| model | car_rental | adventureworks | **BIRD dev** |
| --- | --- | --- | --- |
| gemini-3.7-flash | 100.0% | 100.0% | **63.6%** |
| gemini-3.1-pro-preview | 100.0% | 100.0% | **62.1%** |
| gemini-2.5-flash | 88.6% | 91.8% | **55.7%** |

Three models that were at or near the ceiling on the author's own questions land
in a 56–65% band here, and the band is wide enough to rank them. This is the
headline: **the ceiling §3 could not break is broken by changing whose questions
they are, not by making the SQL harder.**

The difficulty gradient is monotonic in every run, across BIRD's own
`simple`/`moderate`/`challenging` labels, which the harness never sees. Four
independent runs reproducing that ordering is also the evidence that the
scorer is sound.

### 10c. The pro model loses to the flash model

`gemini-3.1-pro-preview` scores **below** `gemini-3.7-flash` at **5× the cost
and 3× the latency** — and the two were indistinguishable on both of the
author's own datasets. The split underneath explains it:

| | simple | moderate | challenging |
| --- | --- | --- | --- |
| pro vs flash | −2.0 | −2.2 | **+1.3** |

Pro genuinely wins where reasoning is required, and loses everywhere else —
and "everywhere else" is 85% of the set. Its error profile says the same thing
from the other side: **1** invalid query against **21** refusals, where flash
emitted 12 invalid and refused 8. Pro is the more cautious model, and caution
costs it more than malformed SQL costs flash.

This is §4's agent-arm result reproducing in a completely different setting:
there, Opus 5 (81.8%) scored below Sonnet 5 (93.2%) and below Haiku 4.5
(84.1%). **Capability does not order the rows, in either experiment.**

### 10d. What BIRD's withheld data dictionary is worth: +1.3 points

BIRD ships a per-column data dictionary it deliberately keeps out of the DDL.
The `financial` database has a column whose `CREATE TABLE` line reads
`A3 TEXT not null` and whose dictionary entry reads `region` — unguessable.

The runs above use **raw DDL only**, keeping the prompt contract byte-identical
to §3's. `bird_dev_dict` adds the dictionary and changes nothing else:

| | prompt tokens | accuracy |
| --- | --- | --- |
| plain DDL | 1,062 | 63.6% |
| + dictionary | 2,600 | **64.9%** |

**+1.3 points for 2.4× the prompt.** And it is not a strict information gain —
per question, the dictionary **fixed 64 and broke 44**, net +20. It helps where
a column name is opaque (`toxicology` +12, `student_club` +10) and hurts where
1,538 extra tokens of column prose crowd the schema with distractors
(`card_games` −9, `financial` −7; `card_games` both gained and lost 9).

Consequence for the writeup: 63.6% is within ~1 point of the
leaderboard-comparable setting, so it can be cited against published BIRD
numbers with a footnote, and the prompt stays identical to the other two
datasets — which is what keeps all three one experiment.

### 10e. Per-database

| database | q | 3.7-flash | 3.1-pro | 2.5-flash |
| --- | --- | --- | --- | --- |
| superhero | 129 | 89.1% | 86.0% | 87.6% |
| debit_card_specializing | 64 | 79.7% | 75.0% | 65.6% |
| student_club | 158 | 76.6% | 77.2% | 69.0% |
| codebase_community | 186 | 73.1% | 74.7% | 71.0% |
| european_football_2 | 129 | 66.7% | 64.3% | 58.1% |
| formula_1 | 174 | 66.1% | 64.9% | 60.9% |
| thrombosis_prediction | 163 | 61.3% | 59.5% | 55.2% |
| card_games | 191 | 55.0% | 54.5% | 49.7% |
| toxicology | 145 | 53.1% | 45.5% | 37.9% |
| california_schools | 89 | **44.9%** | 43.8% | **20.2%** |
| financial | 106 | **28.3%** | **28.3%** | **18.9%** |

Spread of 61 points across databases on one model — far wider than the 8-point
spread between models. **Which database you are asked about matters more than
which model answers**, and `financial` at 28% is where the opaque column names
(`A2`, `A3`, `A11`) live.

### 10f. Why the misses are real, and not a scorer artefact

Every miss in a 30-question stratified probe was re-executed and classified:

| | count |
| --- | --- |
| Genuine wrong answer (right shape, wrong values) | 8 |
| Wrong column set / wrong row count | 4 |
| Model's SQL failed to execute | 1 |
| **Scorer artefact** (BIRD's official metric disagrees) | **1** |

BIRD's official eval compares `set()` of tuples; this harness compares
multisets, so duplicate-row multiplicity is scored here and not there.
Adopting BIRD's exact rule moves the probe 53.3% → 56.7% — one question.

The other 13 are the canonical BIRD failure modes — value grounding and
case-sensitive literals, not SQL construction:

```
gold  WHERE A3 = 'north Bohemia'         → 2260
pred  WHERE A3 = 'North Bohemia'         → 0      ← lowercase 'n' in the data

gold  WHERE Location = 'New York'        → 15
pred  WHERE Location LIKE '%New York%'   → 295

gold  WHERE atom_id LIKE '%_19'          → 498
pred  WHERE atom_id = '19'               → 0      ← ids are TR000_19
```

### 10g. Method notes

- **Every question BIRD ships is included.** All 1,534, no subsetting.
- **Gold validation ran first.** All 1,534 gold queries were executed before any
  model was called. **Zero return empty rows**, so the harness's "an empty gold
  matches any query returning nothing" abort stays armed. Three
  (`b0518`, `b0701`, `b1131`) exceed the 15 s statement timeout; they are
  recorded as `gold_error`, not as model failures, and cost every run the same
  3 points.
- **SQLite, not translated.** BIRD's gold SQL was written against SQLite;
  porting it to PostgreSQL would substitute our SQL for the benchmark's. The
  harness grew a SQLite fixture instead (§11).
- **`evidence` is included**, as BIRD's task definition requires — its questions
  are not answerable without it.
- **Unordered comparison**, matching BIRD's own metric.

---

## 11. Reproducing any number here

```bash
# accuracy / throughput / cost tables, LaTeX bodies
.venv/bin/python benchmark/tables.py
.venv/bin/python benchmark/tables.py --dataset adventureworks

# the local-model tables of §5a
.venv/bin/python benchmark/local_table.py

# BIRD-SQL dev (§10): build the question set from the two upstream artefacts,
# validating every gold query, then run it
.venv/bin/python benchmark_data/bird/prepare.py
./benchmark/sweep_bird.sh                                   # 3 models, parallel
DATASET=bird_dev_dict ./benchmark/sweep_bird.sh gemini-3.7-flash   # + dictionary

# re-run one arm
.venv/bin/python benchmark/run.py --arm naive --model gemini-3.7-flash

# the full unattended local sweep (7 models × 2 datasets)
./benchmark/sweep_local.sh

# start one local model by key
./benchmark/serve_local.sh --list
./benchmark/serve_local.sh qwen36-35b-moe
```

Raw results: `benchmark/results/*.json` (car_rental),
`benchmark/results/adventureworks/*.json`, `benchmark/results/bird_dev/*.json`
and `benchmark/results/bird_dev_dict/*.json`. Every file records its arm, model,
question-set fingerprint, per-question SQL, per-question token usage and
latency. Full discussion and sources: [`research.md`](research.md).

---

## 12. References

Everything the benchmark actually ran against. Split by whether the artefact has
a paper behind it or is a release with only a model card — a distinction worth
keeping, because several of the strongest rows here are the latter and cannot be
cited the same way.

### 12a. Benchmarks and evaluation databases

| artefact | reference |
| --- | --- |
| **BIRD-SQL** (§10) — 12,751 question/SQL pairs, 95 databases, 33.4 GB, 37 domains; the dev split used here is 1,534 questions over 11 databases | Li, J. et al., *Can LLM Already Serve as A Database Interface? A BIg Bench for Large-Scale Database Grounded Text-to-SQLs*, **NeurIPS 2023** (Datasets & Benchmarks). [arXiv:2305.03111](https://arxiv.org/abs/2305.03111) · [bird-bench.github.io](https://bird-bench.github.io/) |
| BIRD dev question revision 2026-11-06 | [`birdsql/bird_sql_dev_20251106`](https://huggingface.co/datasets/birdsql/bird_sql_dev_20251106) (HuggingFace). Questions and gold SQL only |
| BIRD dev database bundle (the 11 SQLite files) | `https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip`, 346 MB. Not on the HuggingFace page; the two artefacts are paired by `benchmark_data/bird/prepare.py` |
| **AdventureWorks** — Microsoft's sample OLTP database | No paper; a Microsoft sample database. PostgreSQL port: [NorfolkDataSci/adventure-works-postgres](https://github.com/NorfolkDataSci/adventure-works-postgres) @ `afcfd2dfcf031af91f03f536c1ade349cfcb3ad6` (pinned). **Ships no question set** — the 56 questions here are written for this thesis |
| **car_rental** | Written for this thesis; schema and generative seed in `test_app_db/` and `benchmark_data/` |

### 12b. Local models under test

The GGUF column is the exact file benchmarked, since a quantisation is part of
the measurement and not an implementation detail.

| model | GGUF file | reference |
| --- | --- | --- |
| **Arctic-Text2SQL-R1-7B** — the SQL specialist; 7B trained with GRPO on an execution-correctness reward, reported top of the BIRD leaderboard in its class | `mradermacher/Arctic-Text2SQL-R1-7B-GGUF`, `Q4_K_M` and `Q8_0` | Yu, Z. et al. (Snowflake AI Research), *Arctic-Text2SQL-R1: Simple Rewards, Strong Reasoning in Text-to-SQL*. [arXiv:2505.20315](https://arxiv.org/abs/2505.20315) · weights [`Snowflake/Arctic-Text2SQL-R1-7B`](https://huggingface.co/Snowflake/Arctic-Text2SQL-R1-7B) · [Snowflake engineering blog](https://www.snowflake.com/en/blog/engineering/arctic-text2sql-r1-sql-generation-benchmark/) |
| Qwen3.5-9B | `lmstudio-community/Qwen3.5-9B-GGUF`, `Q4_K_M` | Release artefact; no technical report located for this specific release |
| Qwen3.6-27B (dense) | `unsloth/Qwen3.6-27B-GGUF`, `UD-IQ3_XXS` and `Q4_K_M` | as above |
| Qwen3.6-35B-A3B (sparse MoE, ~3B active) — the best local result, §5 | `unsloth/Qwen3.6-35B-A3B-GGUF`, `UD-Q4_K_M` | as above |
| Bonsai-27B | `lmstudio-community/Bonsai-27B-GGUF`, `Q1_0` | Release artefact, no paper located. GGUF metadata: `general.basename = prism-ml_Bonsai`, **no `base_model` link** — it shares Qwen3.6-27B's architecture but is not a quantisation of it (§5d) |

### 12c. Hosted models under test

No peer-reviewed papers; these are commercial releases cited by model identifier
and by the rate card in force when the run was made (`prices_checked`
2026-08-23, recorded in every results file).

| vendor | models | used in |
| --- | --- | --- |
| Google | `gemini-2.5-flash`, `gemini-3-flash-preview`, `gemini-3.1-pro-preview`, `gemini-3.6-flash`, `gemini-3.7-flash` | §3 naive, §8 reports, §10 BIRD |
| Anthropic | `claude-opus-5`, `claude-sonnet-5`, `claude-haiku-4-5`, `claude-fable-5` | §4 `claude-agent` |
| OpenAI | `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna` | §4 `codex-agent` |

### 12d. Tooling

| tool | what it did here | reference |
| --- | --- | --- |
| **llama.cpp** | served every local model; LM Studio's CUDA build `cb295bf` | [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp) |
| **PostgreSQL** via `pgserver` | the car_rental / adventureworks fixtures, with no Docker and no system PostgreSQL — which is what makes §2–§8 reproducible by a marker | [pgserver on PyPI](https://pypi.org/project/pgserver/) |
| **SQLite** | the BIRD fixture (§10); BIRD's gold SQL is written against it | [sqlite.org](https://www.sqlite.org/) |
| **Model Context Protocol** | the agentic arms' database access (`list_tables`, `describe_table`, `run_query`) | [modelcontextprotocol.io](https://modelcontextprotocol.io/) |
| Claude Code CLI / Codex CLI | drove the two agent arms as subprocesses, so what is measured is the agent as shipped, default system prompt and all (§4) | — |

### 12e. Literature the method rests on

The design rationale — why these question categories, why execution accuracy,
why the ambiguity questions exist — is argued in
[`research.md`](research.md), whose `## Sources` section carries the full
reading list. The load-bearing ones:

| claim it supports | reference |
| --- | --- |
| Enterprise text-to-SQL is far from solved; the failure taxonomy this benchmark's categories were built from | Spider 2.0 — [arXiv:2411.07763](https://arxiv.org/abs/2411.07763) · [spider2-sql.github.io](https://spider2-sql.github.io/) |
| Grounding, not SQL syntax, is the plateau | BIRD — [arXiv:2305.03111](https://arxiv.org/abs/2305.03111) |
| Text-to-SQL benchmarks have systematic validity problems — the reason §9 and §10g exist | *Text-to-SQL Benchmarks are Broken*, CIDR 2026 — [p5-jin.pdf](https://www.vldb.org/cidrdb/papers/2026/p5-jin.pdf) |
| Enterprise schemas from real query logs | BEAVER — [arXiv:2409.02038](https://arxiv.org/abs/2409.02038) |
| Schema linking may matter less than assumed on small schemas | *The Death of Schema Linking?* — [arXiv:2408.07702](https://arxiv.org/abs/2408.07702) |
| Error taxonomy for generated SQL | NL2SQL-BUGs — [arXiv:2503.11984](https://arxiv.org/abs/2503.11984) |
