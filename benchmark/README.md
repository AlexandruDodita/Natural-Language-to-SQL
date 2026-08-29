# Benchmark

One question set, one database, several ways of answering it. Every arm is
scored the same way, so the numbers in the thesis differ because the approaches
and the models differ and for no other reason.

## Databases

There are two, selected with `--dataset`. They share the arms, the scorer and
the results format, so a number moving between them is attributable to the
schema and nothing else.

| dataset | tables | columns | FKs | rows | schema in prompt |
| --- | --- | --- | --- | --- | --- |
| `car_rental` (default) | 9 | ~70 | 9 | 8,026 | ~1k tokens |
| `adventureworks` | 68 | 1,099 | 91 | ~761k | ~9k tokens |

`car_rental` is the controlled fixture: the whole schema fits in one prompt with
room to spare, so the naive arm sees every table it could possibly need and
retrieval has little to prove. That is what makes it a fair floor, and also what
limits it.

`adventureworks` is Microsoft's sample OLTP database, five schemas wide. At 68
tables the schema is ~9x larger and selecting the right three or four tables
stops being free, which is the part the pipeline exists to do. The question set
is written against that: several questions sit next to a decoy table with
overlapping vocabulary (`salesorderheader` vs `purchaseorderheader`,
`product` vs `productmodel` vs `productsubcategory` vs `productcategory`).

Build it once with:

```sh
python benchmark_data/adventureworks/setup.py
```

That fetches a pinned upstream commit, applies four documented patches needed by
the extension-free `pgserver` build, loads the database and regenerates
`benchmark_data/adventureworks_schema.sql` (the file the naive arm puts in its
prompt). `run.py --dataset adventureworks` runs it automatically if the database
is missing. The CSVs are 102 MB and are fetched rather than committed; the
commit pin is what keeps the build reproducible. See the script's docstring for
what each patch changes and why.

Its evaluation connection sets `search_path` across the five schemas. No table
name is ambiguous between them, so a query that is right in every respect except
for omitting `sales.` still executes -- schema qualification is not what this
benchmark is measuring.

## What is measured

**Execution accuracy** (`score.py`). The generated query and the gold query are
both executed and their result sets compared. Semantically equivalent SQL
counts as correct; this is the metric Spider and BIRD report. `car_rental` has
30 questions of which 26 carry gold SQL; `adventureworks` has 38 of which 34 do.
The remaining 4 in each are deliberately ambiguous and are scored on whether the
system asked for clarification instead of guessing.

Both sets name their output columns in the question ("Show the territory name
and the revenue"), and pin any measure with more than one defensible reading
("revenue from completed payments", not "revenue"). That is not decoration: the
scorer compares result sets and counts an extra column, a missing column or a
different total as a wrong answer, so a question that leaves those open measures
whether the model guessed this file's conventions rather than whether it found
the right tables.

Both sets needed correcting for this. The first draft of the AdventureWorks set
left projections open and scored gemini-2.5-flash at 69%, where every single
miss was a projection mismatch and not one was a wrong join. car_rental had the
same defect in eight questions, and fixing it moved the hosted models from
80.8-96.2% to 96.2-100%. It also shrank the six-run spread on gemini-2.5-flash
from 11.5 points to 3.8: most of what `variance.py` was reporting as sampling
noise was the model re-guessing an under-specified question and landing
differently each time.

The numbers that survive this are worth stating plainly. Once the questions are
unambiguous, the naive whole-schema baseline answers essentially everything on
both databases, and a 7.5x larger schema does not dent it -- what the larger
schema costs is 5.1x the prompt tokens, 2.3-2.8x the money, and clarification on
ambiguous questions, which falls from 13/20 to 3/20 across the same five models.

### Staleness is tracked, not remembered

Every results file records a `questions_fingerprint`: a digest of the question
ids, texts and gold SQL it was scored against. `tables.py` compares it to the
current question set, marks any mismatched row with a `*`, and prints the list
of files to re-run. A file written before this existed carries no fingerprint
and is treated as stale, which is the safe reading.

This exists because the failure it prevents is silent. Rewording a question
invalidates every stored answer to it, but the file still parses and the
percentages still add up -- they just describe a different experiment. A stale
local row sitting in the same LaTeX table as a freshly run hosted row is how a
wrong number reaches print.

### Results regenerated for the revised car_rental questions

Changing a question's wording invalidates any stored answer to it, so every
car_rental result was regenerated against the revised set -- except the arms
whose back ends are not reachable from a bare checkout. These still need
re-running, each against a service that has to be started first:

| file | needs |
| --- | --- |
| `results/pipeline.json` | `rag-service` on :8100 (compose stack) |
| `results/local-*.json` (4) | `llama-server` on :1234 with the gguf model |
| `results/report-qwen3.5-9b*.json`, `results/report-bonsai-27b-q1_0.json` | the same local endpoint |

Everything else -- the five hosted `naive-*` runs, `naive.json`, the four
`repeat/` runs, `mcp-postgres.json`, `variance.json` and the five hosted
`report-*.json` -- was re-run and is current. The `mcp-postgres` arm does not
need Docker: point `DATABASE_URL` at the `pgserver` instance
(`pgserver.get_server("benchmark/.pgdata").get_uri(database="car_rental")`).

**Throughput and tokens** (`clients.py`). Per question: prompt tokens,
completion tokens, reasoning tokens, latency, and two throughput figures --
`tokens_per_sec` (generated tokens over the wall-clock time of the call,
defined identically for hosted and local models, so it is the one the
comparison table uses) and `decode_tokens_per_sec` (the decoder's own rate as
reported by llama.cpp, local only). Time-to-first-token is recorded where the
back end exposes it; llama.cpp reports prefill time, the Gemini SDK does not,
so hosted models fall back to total latency.

**Cost.** Measured token usage extrapolated to a per-100-question API bill,
using the published Gemini rate card. Prices live in
`clients.PRICING_USD_PER_MTOK` with the date they were checked; a model with no
verified price gets no cost estimate rather than an invented one.

**Excel report quality** (`report_score.py`). Chart-type accuracy against the
`expected_chart` field in `questions.yaml`, and structural validity of the
workbook that `rag-service/report.py` actually produces, read back with
openpyxl. The two are reported separately because they fail separately, and
structural validity only means anything read next to chart-type accuracy: it
checks the file against what the model asked for, so a model that asks for no
chart passes it trivially.

`--revalidate <results.json>` redoes only the workbook checks on a finished
run, reusing the chart the model already chose. Building and reading a workbook
is deterministic, so a fix to the checker does not cost another round of model
calls.

## Arms

| arm | what it is |
| --- | --- |
| `naive` | whole schema in one prompt, one hosted call, no retrieval, no repair |
| `local` | the same prompt and contract, answered by a model on this machine over an OpenAI-compatible API |
| `pipeline` | the project's `rag-service` over HTTP |
| `mcp-postgres` | the Postgres MCP server driven agentically |

## Running

Results go to `results/<arm>.json` for `car_rental` and
`results/<dataset>/<arm>.json` for anything else.

```sh
# hosted, one model per results file
GEMINI_API_KEY=... GEMINI_MODEL=gemini-3.7-flash \
  python benchmark/run.py --arm naive --out benchmark/results/naive-gemini-3.7-flash.json

# the same arm and model against the 68-table schema
GEMINI_API_KEY=... GEMINI_MODEL=gemini-3.7-flash \
  python benchmark/run.py --arm naive --dataset adventureworks

# local: start any OpenAI-compatible server first, then point the arm at it
python benchmark/run.py --arm local \
  --local-base-url http://127.0.0.1:1234/v1 --local-model qwen3.5-9b \
  --out benchmark/results/local-qwen3.5-9b.json

# excel report quality
python benchmark/report_score.py --model gemini-3.7-flash
python benchmark/report_score.py --local --local-model qwen3.5-9b

# regenerate the LaTeX table bodies from every results file
python benchmark/tables.py
```

With no `--database-url`, `run.py` starts a throwaway PostgreSQL from the
`pgserver` wheel in `benchmark/.pgdata` and seeds it from the frozen dataset, so
the benchmark needs neither Docker nor a system PostgreSQL.

## Serving a local model

The measurements in the thesis were taken with the `llama-server` binary that
ships inside LM Studio's llama.cpp backend, driven directly. The `lms` CLI could
not be used: it refuses to start its daemon headless on this machine
(`LM Studio daemon is not running and no valid installation could be found`,
because the recorded install path points at a stale AppImage mount), so the
backend is selected by picking the directory to run from.

```sh
# CUDA -- what the headline local numbers were measured on
B=~/.lmstudio/extensions/backends/llama.cpp-linux-x86_64-nvidia-cuda-avx2-2.25.2
V=~/.lmstudio/extensions/backends/vendor/linux-llama-cuda-vendor-v1
LD_LIBRARY_PATH=$B:$V $B/llama-server -m <model>.gguf \
  --host 127.0.0.1 --port 1234 -ngl 99 -c 8192 --device CUDA0 --alias <name>

# Vulkan -- same command, different backend directory and --device Vulkan0
B=~/.lmstudio/extensions/backends/llama.cpp-linux-x86_64-vulkan-avx2-2.25.2
V=~/.lmstudio/extensions/backends/vendor/linux-llama-vulkan-vendor-v1
```

Set `LOCAL_BACKEND` when running the local arm; it is recorded in the results
file. A tokens/sec figure whose backend is not named is not reproducible.

One trap on first use: the CUDA backend appears to hang. On this machine the
first CUDA call after boot stalled for minutes and `llama-server --list-devices`
did not return within 120 s, because the driver was JIT-compiling the bundled
PTX for the RTX 5070's Blackwell architecture. That compilation is cached in
`~/.nv/ComputeCache` (77 MB after the first run) and every later start
enumerates the GPU in under a second. Wait it out rather than concluding the
backend is broken.

## Files

- `datasets.py` -- the evaluation databases; adding one needs no arm changes
- `questions.yaml` -- the car_rental question set, with gold SQL and `expected_chart`
- `questions_adventureworks.yaml` -- the same contract, 68-table schema
- `run.py` -- runs one arm over the set and scores it
- `arms.py` -- the systems under comparison
- `clients.py` -- model access, token accounting, throughput, pricing
- `score.py` -- execution-accuracy comparison
- `report_score.py` -- Excel report chart choice and workbook validation
- `tables.py` -- renders the results as the thesis's LaTeX table bodies
- `results/*.json` -- one file per run
