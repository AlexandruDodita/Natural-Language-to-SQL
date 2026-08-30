#!/usr/bin/env bash
# Start llama-server for one benchmarked local model, with the offload split
# this machine actually needs.
#
#   ./benchmark/serve_local.sh <key>       # start the server on :1234
#   ./benchmark/serve_local.sh --list      # show the keys and why each is here
#
# Hardware this is sized for: RTX 5070, 12 GiB VRAM; 31 GiB system RAM;
# i9-14900K (32 threads). The VRAM number is the binding constraint and it is
# what every -ngl below is derived from: a model whose weights exceed ~11 GiB
# cannot be fully resident once the KV cache is allowed for, so the layer count
# is cut until it fits and the rest runs on the CPU. A model that spills is not
# broken, it is slow, and the tokens/sec column is where that shows up.
#
# LOCAL_BACKEND is exported into the environment run.py records, because a
# throughput figure whose backend is not named is not reproducible.
set -euo pipefail

MODELS=~/models
B=~/.lmstudio/extensions/backends/llama.cpp-linux-x86_64-nvidia-cuda-avx2-2.25.2
V=~/.lmstudio/extensions/backends/vendor/linux-llama-cuda-vendor-v1
PORT=${PORT:-1234}
CTX=${CTX:-16384}

case "${1:-}" in
  arctic-7b-q4)
    # The text-to-SQL specialist: Snowflake's Arctic-Text2SQL-R1, 68.5% on BIRD,
    # the only 7B in that leaderboard's top tier. Fits VRAM whole, so it is the
    # one local arm whose speed is not an artefact of offloading.
    M=$MODELS/mradermacher/Arctic-Text2SQL-R1-7B-GGUF/Arctic-Text2SQL-R1-7B.Q4_K_M.gguf; NGL=99 ;;
  arctic-7b-q8)
    # The same weights at near-lossless quantisation. Paired with the Q4 row it
    # separates "this model is weak" from "this quantisation is lossy".
    M=$MODELS/mradermacher/Arctic-Text2SQL-R1-7B-GGUF/Arctic-Text2SQL-R1-7B.Q8_0.gguf; NGL=99 ;;
  qwen35-9b)
    # Already benchmarked in the first wave; kept so the second-wave numbers
    # have a comparable row.
    M=$MODELS/lmstudio-community/Qwen3.5-9B-GGUF/Qwen3.5-9B-Q4_K_M.gguf; NGL=99 ;;
  bonsai-27b-q1)
    # 27B at 1.125 bits per weight. The interesting end of the quantisation
    # ladder: same base model as qwen36-27b-*, one eighth the file.
    M=$MODELS/lmstudio-community/Bonsai-27B-GGUF/Bonsai-27B-Q1_0.gguf; NGL=99 ;;
  qwen36-27b-iq3)
    # The largest Qwen3.6-27B quant that still (just) fits: 11.99 GiB of weights
    # against 11.94 GiB of usable VRAM, so a few layers still spill once the KV
    # cache is allocated. Lower CTX if it OOMs rather than cutting NGL further.
    M=$MODELS/unsloth/Qwen3.6-27B-GGUF/Qwen3.6-27B-UD-IQ3_XXS.gguf; NGL=58 ;;
  qwen36-27b-q4)
    # The Q4 baseline Bonsai is a compression of. 16.8 GiB: roughly two thirds
    # of the layers on the GPU, the rest on the CPU.
    M=$MODELS/unsloth/Qwen3.6-27B-GGUF/Qwen3.6-27B-Q4_K_M.gguf; NGL=40 ;;
  qwen36-35b-moe)
    # 35B total, ~3B active per token. For a MoE the right split is not "fewer
    # layers" but "experts on the CPU, attention on the GPU" -- --n-cpu-moe does
    # exactly that, which is why this row keeps NGL high despite being the
    # largest file here.
    M=$MODELS/unsloth/Qwen3.6-35B-A3B-GGUF/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf
    NGL=99; EXTRA="--n-cpu-moe 28" ;;
  --list|"")
    grep -E "^  [a-z0-9-]+\)" "$0" | tr -d ' )' | sed 's/^/  /'
    exit 0 ;;
  *) echo "unknown model key: $1 (try --list)" >&2; exit 1 ;;
esac

[ -f "$M" ] || { echo "missing model file: $M" >&2; exit 1; }
echo "serving $(basename "$M")  ngl=$NGL ctx=$CTX port=$PORT"
export LD_LIBRARY_PATH=$B:$V
exec "$B/llama-server" -m "$M" --host 127.0.0.1 --port "$PORT" \
     -ngl "$NGL" -c "$CTX" --device CUDA0 --alias "$1" ${EXTRA:-}
