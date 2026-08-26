"""Structured per-request telemetry (JSONL).

One JSON object per request, appended to a file. It carries everything the
evaluation chapter aggregates: the question, the retrieved tables, every SQL
attempt with its error, the final SQL, the row count, per-stage latency, the
retry count, policy events and the final outcome.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


# Outcomes are a closed vocabulary so results tables can be built by grouping.
OUTCOME_ANSWERED = "answered"
OUTCOME_NO_SQL = "no_sql"
OUTCOME_CLARIFICATION = "clarification"
OUTCOME_BLOCKED_POLICY = "blocked_by_policy"
OUTCOME_VALIDATION_FAILED = "validation_failed"
OUTCOME_EXECUTION_FAILED = "execution_failed"
OUTCOME_GENERATION_FAILED = "generation_failed"


@dataclass
class Attempt:
    index: int
    sql: Optional[str] = None
    stage: str = "generation"  # generation | validation | policy | dry_run | execution
    ok: bool = False
    error: Optional[str] = None
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RequestTrace:
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    question: str = ""
    user: dict = field(default_factory=dict)
    retrieval: dict = field(default_factory=dict)
    attempts: list[Attempt] = field(default_factory=list)
    final_sql: Optional[str] = None
    row_count: Optional[int] = None
    outcome: str = ""
    error: Optional[str] = None
    clarification: Optional[str] = None
    policy: dict = field(default_factory=dict)
    chart: Optional[dict] = None
    stages: dict[str, float] = field(default_factory=dict)
    knobs: dict = field(default_factory=dict)
    model: str = ""

    @property
    def retries(self) -> int:
        return max(0, len({a.index for a in self.attempts}) - 1)

    @property
    def total_ms(self) -> float:
        return round(sum(self.stages.values()), 2)

    @contextmanager
    def stage(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = (time.perf_counter() - start) * 1000.0
            self.stages[name] = round(self.stages.get(name, 0.0) + elapsed, 2)

    def add_attempt(self, attempt: Attempt) -> None:
        self.attempts.append(attempt)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["attempts"] = [a.to_dict() for a in self.attempts]
        data["retries"] = self.retries
        data["total_ms"] = self.total_ms
        return data


class Telemetry:
    def __init__(self, path: str, enabled: bool = True):
        self.path = path
        self.enabled = enabled
        self._lock = threading.Lock()
        if enabled:
            try:
                os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            except OSError as exc:  # pragma: no cover
                logger.warning("telemetry disabled: %s", exc)
                self.enabled = False

    def record(self, trace: RequestTrace) -> None:
        if not self.enabled:
            return
        line = json.dumps(trace.to_dict(), default=str)
        try:
            with self._lock, open(self.path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError as exc:  # pragma: no cover
            logger.warning("could not write telemetry: %s", exc)

    def read_all(self) -> list[dict]:
        try:
            with open(self.path, encoding="utf-8") as fh:
                out = []
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            out.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
                return out
        except OSError:
            return []

    def recent(self, limit: int = 20) -> list[dict]:
        return self.read_all()[-limit:]

    def summary(self) -> dict:
        records = self.read_all()
        if not records:
            return {"requests": 0}

        outcomes: dict[str, int] = {}
        stage_totals: dict[str, float] = {}
        stage_counts: dict[str, int] = {}
        retries = 0
        repaired_ok = 0
        blocked = 0

        for rec in records:
            outcome = rec.get("outcome", "unknown")
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
            retries += rec.get("retries", 0)
            if rec.get("retries", 0) > 0 and outcome == OUTCOME_ANSWERED:
                repaired_ok += 1
            if outcome == OUTCOME_BLOCKED_POLICY:
                blocked += 1
            for name, value in (rec.get("stages") or {}).items():
                stage_totals[name] = stage_totals.get(name, 0.0) + value
                stage_counts[name] = stage_counts.get(name, 0) + 1

        n = len(records)
        return {
            "requests": n,
            "outcomes": outcomes,
            "success_rate": round(outcomes.get(OUTCOME_ANSWERED, 0) / n, 4),
            "avg_retries": round(retries / n, 4),
            "repaired_after_retry": repaired_ok,
            "blocked_by_policy": blocked,
            "avg_stage_ms": {
                name: round(total / stage_counts[name], 2)
                for name, total in stage_totals.items()
            },
        }
