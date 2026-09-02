"""Execution-accuracy scoring.

A generated query is correct when executing it produces the same result set as
executing the gold query. Comparing results rather than SQL text is what makes
the metric fair: there are many correct ways to write the same join, and a
string or AST comparison would fail most of them. This is the metric Spider and
BIRD report.

Normalisation is deliberately narrow. Numeric types are unified and rounded
(Decimal(3.0) and float 3.0 are the same answer; 1234.5678 and 1234.5679 are
not meaningfully different at 4dp), dates become ISO strings, and column NAMES
are ignored because aliasing is a stylistic choice. Column COUNT and row
multiplicity are not ignored: returning an extra column, or losing duplicate
rows to a stray DISTINCT, is a different answer.
"""

from __future__ import annotations

import datetime
import decimal
from typing import Any, Iterable, Sequence

ROUND_DP = 4


def _norm(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float, decimal.Decimal)):
        # Unify the numeric tower, then round: engines differ in whether a SUM
        # comes back as Decimal, float or int, and that is not a semantic
        # difference. Integral values collapse to int so 3 == 3.0 == Decimal(3).
        f = round(float(v), ROUND_DP)
        return int(f) if f == int(f) else f
    if isinstance(v, datetime.datetime):
        # Drop any offset first: PostgreSQL hands back TIMESTAMPTZ for some
        # expressions and naive timestamps for others, and that is a storage
        # detail, not a different answer.
        if v.tzinfo is not None:
            v = v.replace(tzinfo=None)
        # A timestamp at exact midnight and the corresponding date are the same
        # answer. DATE_TRUNC('month', ...) yields a timestamp while models
        # routinely CAST(... AS DATE); scoring those as different penalised
        # every model on the monthly-series question for a difference of
        # representation rather than of result.
        if (v.hour, v.minute, v.second, v.microsecond) == (0, 0, 0, 0):
            return v.date().isoformat()
        return v.replace(microsecond=0).isoformat(sep=" ")
    if isinstance(v, datetime.date):
        return v.isoformat()
    if isinstance(v, str):
        return v.strip()
    return str(v)


def _norm_rows(rows: Iterable[Sequence[Any]]) -> list[tuple]:
    return [tuple(_norm(v) for v in row) for row in rows]


def _sortable(rows: list[tuple]) -> list:
    # Rows can mix None with numbers and strings, which is unorderable in
    # Python 3. Sorting by the repr gives a stable, total order that is only
    # ever used to make an order-insensitive comparison deterministic.
    return sorted(rows, key=repr)


def result_sets_match(
    gold_rows: Iterable[Sequence[Any]],
    pred_rows: Iterable[Sequence[Any]],
    ordered: bool = False,
) -> bool:
    """True when the two result sets are the same answer.

    `ordered` must be set for questions whose wording makes order part of the
    answer ("top ten", "ranked by"). Otherwise rows are compared as a multiset,
    so an arbitrary ORDER BY difference does not count against a correct query.
    """
    g = _norm_rows(gold_rows)
    p = _norm_rows(pred_rows)

    if len(g) != len(p):
        return False
    if g and p and len(g[0]) != len(p[0]):
        return False
    if ordered:
        return g == p
    return _sortable(g) == _sortable(p)


def summarise(results: list[dict]) -> dict:
    """Aggregate per-question results into the numbers the thesis reports."""
    scored = [r for r in results if r.get("scored")]
    by_cat: dict[str, list[dict]] = {}
    for r in scored:
        by_cat.setdefault(r["category"], []).append(r)

    def acc(rs: list[dict]) -> float:
        return (sum(1 for r in rs if r["correct"]) / len(rs)) if rs else 0.0

    latencies = sorted(r["latency_ms"] for r in results if r.get("latency_ms"))
    ambiguous = [r for r in results if not r.get("scored")]

    return {
        "n_scored": len(scored),
        "n_correct": sum(1 for r in scored if r["correct"]),
        "execution_accuracy": round(acc(scored), 4),
        "by_category": {
            c: {"n": len(rs), "correct": sum(1 for r in rs if r["correct"]), "accuracy": round(acc(rs), 4)}
            for c, rs in sorted(by_cat.items())
        },
        "invalid_sql": sum(1 for r in scored if r.get("exec_error")),
        "no_sql_produced": sum(1 for r in scored if not r.get("sql")),
        # Questions whose own gold SQL would not execute. They count as wrong
        # for every arm alike, so they depress the whole column by the same
        # amount rather than separating any two rows -- but a reader comparing
        # against a published figure needs to know they are in the denominator.
        "gold_unscoreable": sum(1 for r in scored if r.get("gold_error")),
        # Ambiguous questions are not scored for accuracy; what matters is
        # whether the system asked instead of guessing.
        "ambiguous_total": len(ambiguous),
        "ambiguous_clarified": sum(1 for r in ambiguous if r.get("clarified")),
        "latency_ms_median": latencies[len(latencies) // 2] if latencies else None,
        "latency_ms_mean": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "usage": _usage_summary(results),
    }


def _usage_summary(results: list[dict]) -> dict:
    """Aggregate the per-question token/throughput records.

    Derived from the per-question `usage` entries rather than accumulated during
    the run, so a results file can be re-scored or re-aggregated later without
    re-calling any model - which is what keeps a scorer change from being
    entangled with fresh sampling noise.
    """
    us = [r["usage"] for r in results if r.get("usage")]
    if not us:
        return {}

    def vals(key):
        return [u[key] for u in us if u.get(key) is not None]

    def mean(key):
        v = vals(key)
        return round(sum(v) / len(v), 2) if v else None

    def total(key):
        v = vals(key)
        return sum(v) if v else None

    def median(key):
        v = sorted(vals(key))
        return v[len(v) // 2] if v else None

    # Gemini bills reasoning ("thinking") tokens at the output rate and does not
    # include them in completion_tokens. Counting only completion_tokens
    # understated the pro model's generated volume by ~15x and its cost by more
    # than half, so billed output is completion + thinking.
    billed = [
        (u.get("completion_tokens") or 0) + (u.get("thinking_tokens") or 0)
        for u in us
    ]
    billed = [b for b in billed if b]

    return {
        "n": len(us),
        "tokens_per_sec_mean": mean("tokens_per_sec"),
        "decode_tokens_per_sec_mean": mean("decode_tokens_per_sec"),
        "ttft_ms_median": median("ttft_ms"),
        "prompt_tokens_mean": mean("prompt_tokens"),
        "output_tokens_mean": round(sum(billed) / len(billed), 2) if billed else None,
        "completion_tokens_mean": mean("completion_tokens"),
        "prompt_tokens_total": total("prompt_tokens"),
        "output_tokens_total": sum(billed) if billed else None,
        "thinking_tokens_total": total("thinking_tokens"),
    }
