"""Model access for the benchmark, with the cost and throughput instrumentation.

The arms differ in *how* they use a model; this module is the single place that
knows how to *call* one. Both back ends return the same ``Usage`` record, which
is what makes the hosted-versus-local table in the thesis a comparison of models
rather than a comparison of two different measurement methods.

Two throughput figures are recorded on purpose:

``tokens_per_sec``
    generated tokens divided by the wall-clock time of the whole call. This is
    the number a user feels, it is defined identically for a hosted model and a
    local one, and it is therefore the one the comparison table reports.
``decode_tokens_per_sec``
    the decoder's own rate, reported by llama.cpp in its ``timings`` block. It
    excludes prompt processing and queueing, so it is higher than the
    end-to-end figure, and it exists only for the local back end. It is kept
    because it is the number that characterises the hardware rather than the
    deployment.

"Generated tokens" means completion tokens plus reasoning tokens. Every model
measured here is a reasoning model to some degree, and the hidden tokens are
both paid for and waited for; charging them to throughput and to cost is the
honest accounting.
"""

from __future__ import annotations

import dataclasses
import json
import os
import time
from typing import Any, Optional


@dataclasses.dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    thinking_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    ttft_ms: Optional[float] = None
    tokens_per_sec: Optional[float] = None
    decode_tokens_per_sec: Optional[float] = None
    finish_reason: Optional[str] = None

    @property
    def output_tokens(self) -> int:
        """Everything the model generated, hidden reasoning included."""
        return self.completion_tokens + self.thinking_tokens

    def as_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["output_tokens"] = self.output_tokens
        return d


def _rate(tokens: int, ms: float) -> Optional[float]:
    return round(tokens / (ms / 1000.0), 2) if tokens and ms > 0 else None


# ---------------------------------------------------------------------------
# Hosted: Google Gemini
# ---------------------------------------------------------------------------
def gemini_model_name() -> str:
    return os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


# A transient API failure used to cost a question permanently: the arm catches
# the exception, records it, and moves on. On a 44-question set that was a
# tolerable rarity. On BIRD's 1,534 -- three of them running at once for hours --
# a rate-limit burst would silently subtract several points from a row, and the
# lost questions would be indistinguishable from questions the model got wrong.
RETRY_ATTEMPTS = int(os.environ.get("GEMINI_RETRY_ATTEMPTS", "4"))
RETRY_BASE_S = float(os.environ.get("GEMINI_RETRY_BASE_S", "2.0"))
# Substrings of the exceptions worth retrying. A safety block or a malformed
# request will fail identically however many times it is sent, and retrying
# those would just multiply the wait before recording the real error.
_TRANSIENT = ("429", "500", "502", "503", "504", "deadline", "timeout",
              "unavailable", "resource has been exhausted", "internal error",
              "connection", "quota")


def _is_transient(e: Exception) -> bool:
    s = f"{type(e).__name__}: {e}".lower()
    return any(k in s for k in _TRANSIENT)


def gemini_complete(prompt: str, model: Optional[str] = None) -> tuple[str, Usage]:
    """One non-streaming completion. Returns the text and its usage record.

    Retries transient failures with exponential backoff. The latency recorded is
    that of the attempt that succeeded, not of the whole retry sequence: the
    throughput column measures how fast the model answers, and folding a
    backoff sleep into it would make a rate-limited run look like a slow model.
    """
    import google.generativeai as genai

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    name = model or gemini_model_name()
    for attempt in range(RETRY_ATTEMPTS):
        try:
            t0 = time.perf_counter()
            resp = genai.GenerativeModel(name).generate_content(prompt)
            dt = (time.perf_counter() - t0) * 1000
            break
        except Exception as e:
            if attempt == RETRY_ATTEMPTS - 1 or not _is_transient(e):
                raise
            time.sleep(RETRY_BASE_S * (2 ** attempt))

    um = getattr(resp, "usage_metadata", None)
    prompt_tok = int(getattr(um, "prompt_token_count", 0) or 0)
    completion_tok = int(getattr(um, "candidates_token_count", 0) or 0)
    total_tok = int(getattr(um, "total_token_count", 0) or 0)
    # The SDK only exposes thoughts_token_count on models that report it; where
    # it is absent the residual of the total is the thinking budget spent.
    thinking_tok = int(getattr(um, "thoughts_token_count", 0) or 0)
    if not thinking_tok and total_tok > prompt_tok + completion_tok:
        thinking_tok = total_tok - prompt_tok - completion_tok

    finish = None
    try:
        finish = str(resp.candidates[0].finish_reason)
    except Exception:
        pass

    u = Usage(
        prompt_tokens=prompt_tok,
        completion_tokens=completion_tok,
        thinking_tokens=thinking_tok,
        total_tokens=total_tok or (prompt_tok + completion_tok + thinking_tok),
        latency_ms=round(dt, 1),
        finish_reason=finish,
    )
    u.tokens_per_sec = _rate(u.output_tokens, dt)
    return (resp.text or ""), u


# ---------------------------------------------------------------------------
# Local: any OpenAI-compatible server (llama.cpp / LM Studio / vLLM / Ollama)
# ---------------------------------------------------------------------------
DEFAULT_LOCAL_BASE_URL = os.environ.get("LOCAL_BASE_URL", "http://127.0.0.1:1234/v1")
DEFAULT_LOCAL_MODEL = os.environ.get("LOCAL_MODEL", "local-model")
LOCAL_MAX_TOKENS = int(os.environ.get("LOCAL_MAX_TOKENS", "2048"))
# Free-text description of the inference engine behind the endpoint, recorded in
# the results file. A tokens/sec figure whose backend is not named is not
# reproducible: the same GPU and the same GGUF decode at different rates under
# llama.cpp's CUDA, Vulkan and CPU backends.
LOCAL_BACKEND = os.environ.get("LOCAL_BACKEND")
LOCAL_TIMEOUT_S = float(os.environ.get("LOCAL_TIMEOUT_S", "600"))


def local_complete(
    prompt: str,
    base_url: str = DEFAULT_LOCAL_BASE_URL,
    model: str = DEFAULT_LOCAL_MODEL,
    max_tokens: int = LOCAL_MAX_TOKENS,
) -> tuple[str, Usage]:
    """One non-streaming chat completion against an OpenAI-compatible endpoint.

    Deliberately a single user message with no system prompt, so the local arm
    sends the byte-identical prompt the hosted arm sends.
    """
    import httpx

    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": False,
    }
    t0 = time.perf_counter()
    with httpx.Client(timeout=LOCAL_TIMEOUT_S) as c:
        r = c.post(f"{base_url.rstrip('/')}/chat/completions", json=payload)
        r.raise_for_status()
        body = r.json()
    dt = (time.perf_counter() - t0) * 1000

    choice = (body.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    text = msg.get("content") or ""
    reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""

    usage = body.get("usage") or {}
    prompt_tok = int(usage.get("prompt_tokens") or 0)
    completion_tok = int(usage.get("completion_tokens") or 0)
    details = usage.get("completion_tokens_details") or {}
    thinking_tok = int(details.get("reasoning_tokens") or 0)
    if thinking_tok:
        # OpenAI's convention counts reasoning inside completion_tokens; the
        # Usage record keeps them in separate fields, so subtract it back out.
        completion_tok = max(0, completion_tok - thinking_tok)

    u = Usage(
        prompt_tokens=prompt_tok,
        completion_tokens=completion_tok,
        thinking_tokens=thinking_tok,
        total_tokens=int(usage.get("total_tokens") or (prompt_tok + completion_tok + thinking_tok)),
        latency_ms=round(dt, 1),
        finish_reason=choice.get("finish_reason"),
    )
    u.tokens_per_sec = _rate(u.output_tokens, dt)

    timings = body.get("timings") or {}
    if timings:
        # llama.cpp: prompt_ms is prefill, which ends when the first token is
        # emitted, so it is the time-to-first-token of a non-streaming call.
        if timings.get("prompt_ms") is not None:
            u.ttft_ms = round(float(timings["prompt_ms"]), 1)
        if timings.get("predicted_per_second") is not None:
            u.decode_tokens_per_sec = round(float(timings["predicted_per_second"]), 2)

    if not text and reasoning:
        # The model spent its whole budget thinking and never produced an
        # answer. Surfacing this as an empty completion (rather than salvaging
        # SQL out of the reasoning trace) is what makes it visible in the
        # results as the failure mode it is.
        text = ""
    return text, u


# ---------------------------------------------------------------------------
# Cost
# ---------------------------------------------------------------------------
# USD per 1 000 000 tokens, from ai.google.dev/gemini-api/docs/pricing (paid
# tier, prompts under the long-context threshold). Output pricing covers
# reasoning tokens as well as visible ones. Verified on the date in
# PRICING_CHECKED; a model absent from this table gets no cost estimate rather
# than a guessed one.
PRICING_CHECKED = "2026-08-23"
PRICING_USD_PER_MTOK: dict[str, dict[str, float]] = {
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    # Promotional rate, listed as valid through 31 December 2026 and doubling
    # to 1.50/7.50 afterwards. The benchmark reports the rate in force when it
    # was run.
    "gemini-3.7-flash": {"input": 0.75, "output": 3.75},
    "gemini-3.6-flash": {"input": 0.75, "output": 3.75},
    "gemini-3-flash-preview": {"input": 0.50, "output": 3.00},
    # Tiered by prompt length; every prompt in this benchmark is far below the
    # 200k-token threshold, so the lower tier is the applicable one.
    "gemini-3.1-pro-preview": {"input": 2.00, "output": 12.00},
    # Anthropic list rates, for the agent arm. These are the sticker prices and
    # they OVERSTATE what that arm actually costs: an agent re-sends a large
    # cached prefix every turn, and cache reads bill at a fraction of the input
    # rate. The arm records the CLI's own cache-aware figure per question, which
    # is what `usd_per_100_questions_measured` reports; this row exists so the
    # extrapolated column is not simply blank, and the two should be read
    # together.
    "claude-fable-5": {"input": 10.00, "output": 50.00},
    "claude-opus-5": {"input": 5.00, "output": 25.00},
    "claude-sonnet-5": {"input": 2.00, "output": 10.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    # A locally served model has no per-token price. Zero here means "no API
    # invoice", not "free": the hardware and the electricity are the cost, and
    # the thesis discusses them separately.
    "local": {"input": 0.0, "output": 0.0},
}


def estimate_cost_usd(model: str, prompt_tokens: int, output_tokens: int) -> Optional[float]:
    """Cost of a token bundle, or None when the model has no verified price."""
    p = PRICING_USD_PER_MTOK.get(model)
    if not p:
        return None
    return (prompt_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


def aggregate_usage(records: list[dict]) -> dict:
    """Token/throughput aggregates over a list of per-question usage dicts."""
    us = [r for r in records if r]
    if not us:
        return {}

    def col(k: str) -> list[float]:
        return [float(r[k]) for r in us if r.get(k) is not None]

    def med(xs: list[float]) -> Optional[float]:
        return round(sorted(xs)[len(xs) // 2], 2) if xs else None

    def mean(xs: list[float]) -> Optional[float]:
        return round(sum(xs) / len(xs), 2) if xs else None

    prompt_tok = col("prompt_tokens")
    out_tok = col("output_tokens")
    return {
        "n": len(us),
        "prompt_tokens_total": int(sum(prompt_tok)),
        "prompt_tokens_mean": mean(prompt_tok),
        "completion_tokens_total": int(sum(col("completion_tokens"))),
        "thinking_tokens_total": int(sum(col("thinking_tokens"))),
        "output_tokens_total": int(sum(out_tok)),
        "output_tokens_mean": mean(out_tok),
        "total_tokens_total": int(sum(col("total_tokens"))),
        "tokens_per_sec_mean": mean(col("tokens_per_sec")),
        "tokens_per_sec_median": med(col("tokens_per_sec")),
        "decode_tokens_per_sec_mean": mean(col("decode_tokens_per_sec")),
        "ttft_ms_median": med(col("ttft_ms")),
    }
