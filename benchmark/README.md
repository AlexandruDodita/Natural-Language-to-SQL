# Benchmark

One question set, one database, several ways of answering it. Every arm is
scored the same way, so the numbers in the thesis differ because the approaches
and the models differ and for no other reason.

## What is measured

**Execution accuracy** (`score.py`). The generated query and the gold query are
both executed and their result sets compared. Semantically equivalent SQL
counts as correct; this is the metric Spider and BIRD report. 26 of the 30
questions carry gold SQL. The other 4 are deliberately ambiguous and are scored
on whether the system asked for clarification instead of guessing.

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

```sh
# hosted, one model per results file
GEMINI_API_KEY=... GEMINI_MODEL=gemini-3.7-flash \
  python benchmark/run.py --arm naive --out benchmark/results/naive-gemini-3.7-flash.json

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

- `questions.yaml` -- the question set, with gold SQL and `expected_chart`
- `run.py` -- runs one arm over the set and scores it
- `arms.py` -- the systems under comparison
- `clients.py` -- model access, token accounting, throughput, pricing
- `score.py` -- execution-accuracy comparison
- `report_score.py` -- Excel report chart choice and workbook validation
- `tables.py` -- renders the results as the thesis's LaTeX table bodies
- `results/*.json` -- one file per run
