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
        # Ambiguous questions are not scored for accuracy; what matters is
        # whether the system asked instead of guessing.
        "ambiguous_total": len(ambiguous),
        "ambiguous_clarified": sum(1 for r in ambiguous if r.get("clarified")),
        "latency_ms_median": latencies[len(latencies) // 2] if latencies else None,
        "latency_ms_mean": round(sum(latencies) / len(latencies), 1) if latencies else None,
    }
