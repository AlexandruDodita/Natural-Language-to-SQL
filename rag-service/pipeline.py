"""Orchestration: retrieve -> generate -> validate -> authorize -> dry-run -> execute.

Everything that can fail feeds back into the model exactly once per retry
budget slot, together with the *verbatim* database error, which is the
execution-feedback self-repair loop. Policy violations are deliberately
terminal: the user is told the request was refused rather than the model being
invited to find a way around the rule.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import llm as llm_mod
from db import QueryResult, SessionContext, SqlExecutionError
from policy import PolicyEngine, PolicyError, UserContext
from telemetry import (
    Attempt,
    OUTCOME_ANSWERED,
    OUTCOME_BLOCKED_POLICY,
    OUTCOME_CLARIFICATION,
    OUTCOME_EXECUTION_FAILED,
    OUTCOME_GENERATION_FAILED,
    OUTCOME_NO_SQL,
    OUTCOME_VALIDATION_FAILED,
    RequestTrace,
)
from validator import SqlValidator

logger = logging.getLogger(__name__)


@dataclass
class PipelineOutcome:
    trace: RequestTrace
    outcome: str
    sql_meta: dict = field(default_factory=dict)
    data_payload: Optional[dict] = None
    answer_prompt: str = ""
    question: str = ""
    history: list[dict] = field(default_factory=list)
    clarification: Optional[str] = None


def format_results(result: QueryResult) -> str:
    """Compact markdown table handed to the answering model."""
    if not result.columns:
        return f"Query returned no rows. ({result.duration_ms:.1f} ms)"
    header = " | ".join(result.columns)
    separator = " | ".join(["---"] * len(result.columns))
    body = "\n".join(
        f"| {' | '.join('' if c is None else str(c) for c in row)} |"
        for row in result.rows
    )
    return (
        f"Query returned {result.row_count} row(s) in {result.duration_ms:.1f} ms:\n\n"
        f"| {header} |\n| {separator} |\n{body}"
    )


@dataclass
class DirectSqlOutcome:
    """Result of running a SQL string the user supplied (SQL tab, history re-run).

    No model is involved, but the query still goes through the same validator and
    the same policy rewrite as a generated one — which is the point: editing the
    SQL in the workbench cannot widen what the role is allowed to read.
    """

    ok: bool = False
    sql: Optional[str] = None
    stage: Optional[str] = None  # validation | policy | execution
    error: Optional[str] = None
    validation: dict = field(default_factory=dict)
    policy: dict = field(default_factory=dict)
    columns: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    row_count: int = 0
    duration_ms: float = 0.0
    truncated: bool = False
    plan: list[str] = field(default_factory=list)
    max_rows: int = 0
    role: str = ""

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "sql": self.sql,
            "stage": self.stage,
            "error": self.error,
            "validation": self.validation,
            "policy": self.policy,
            "columns": self.columns,
            "rows": self.rows,
            "row_count": self.row_count,
            "duration_ms": self.duration_ms,
            "truncated": self.truncated,
            "plan": self.plan,
            "max_rows": self.max_rows,
            "role": self.role,
        }


def _clean_options(raw: Any) -> list[dict]:
    """Normalise the optional ``options`` array of a clarification response.

    The model is asked for one entry per reading, each naming the measure
    expression it would use. Anything malformed is dropped rather than raised:
    the prose clarification is the contract, the options are an enrichment.
    """
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw[:5]:
        if not isinstance(item, dict):
            continue
        label = item.get("label") or item.get("title")
        if not label:
            continue
        out.append(
            {
                "label": str(label)[:120],
                "measure": str(item.get("measure") or "")[:200] or None,
                "note": str(item.get("note") or "")[:200] or None,
                "question": str(item.get("question") or "")[:300] or None,
            }
        )
    return out


def split_messages(messages: list) -> tuple[list[dict], str, str]:
    """Return (gemini history, condensed history text, last user message)."""
    history: list[dict] = []
    for msg in messages[:-1]:
        role = "model" if msg.role == "assistant" else "user"
        history.append({"role": role, "parts": [msg.content]})

    lines = []
    for msg in history[-6:]:
        who = "Assistant" if msg["role"] == "model" else "User"
        lines.append(f"{who}: {msg['parts'][0][:200]}".replace("\n", " "))
    history_text = "\n".join(lines)
    return history, history_text, messages[-1].content


class Pipeline:
    def __init__(
        self,
        settings,
        state,
        telemetry,
    ):
        self.settings = settings
        self.state = state  # ServiceState (schema index, runners, policy, llm)
        self.telemetry = telemetry

    # -- helpers ----------------------------------------------------------
    def _validator(self, ctx: UserContext) -> SqlValidator:
        max_rows = self.settings.max_rows
        if self.state.policy is not None:
            role_max = self.state.policy.max_rows(ctx)
            if role_max:
                max_rows = min(max_rows, int(role_max))
        known = self.state.catalog.table_names if self.state.catalog else []
        return SqlValidator(
            dialect=self.settings.sql_dialect,
            max_rows=max_rows,
            known_tables=known,
            enforce_known_tables=bool(known),
        )

    def _session(self, ctx: UserContext) -> SessionContext:
        db_role = self.state.policy.db_role(ctx) if self.state.policy else None
        return SessionContext(
            role=db_role, location_id=ctx.location_id, user_id=ctx.user_id
        )

    def _hidden_columns(self, ctx: UserContext) -> list[str]:
        if self.state.policy is None:
            return []
        return list(self.state.policy.role(ctx.role).denied_columns)

    # -- user-supplied SQL -------------------------------------------------
    async def run_sql(
        self, sql: str, ctx: UserContext, explain: bool = False
    ) -> DirectSqlOutcome:
        """Validate, authorize and run a SQL string that did not come from the model.

        Deliberately not recorded in telemetry: the evaluation chapter counts
        model-generated requests, and a manual re-run is not one.
        """
        validator = self._validator(ctx)
        session = self._session(ctx)
        out = DirectSqlOutcome(max_rows=validator.max_rows, role=ctx.role)

        validation = validator.validate(sql)
        out.validation = validation.to_dict()
        if not validation.ok:
            out.stage = "validation"
            out.error = validation.error
            return out
        safe_sql = validation.sql

        if self.state.policy is not None and self.settings.policy_enabled:
            try:
                policy_result = self.state.policy.rewrite(safe_sql, ctx)
            except PolicyError as exc:
                out.stage = "policy"
                out.error = str(exc)
                return out
            out.policy = policy_result.to_dict()
            if not policy_result.ok:
                out.stage = "policy"
                out.error = policy_result.blocked_reason
                return out
            safe_sql = policy_result.sql

        out.sql = safe_sql

        if explain:
            if not self.state.can_explain:
                out.stage = "execution"
                out.error = "EXPLAIN is unavailable with the current SQL executor"
                return out
            try:
                plan = await self.state.direct_runner.execute(
                    f"EXPLAIN {safe_sql}", session=session
                )
            except SqlExecutionError as exc:
                out.stage = "execution"
                out.error = str(exc)
                return out
            out.plan = [
                " ".join("" if c is None else str(c) for c in row) for row in plan.rows
            ]
            out.duration_ms = plan.duration_ms
            out.ok = True
            return out

        try:
            result = await self.state.execute(safe_sql, session)
        except SqlExecutionError as exc:
            out.stage = "execution"
            out.error = str(exc)
            return out
        except Exception as exc:  # pragma: no cover - unexpected
            out.stage = "execution"
            out.error = str(exc)
            return out

        out.ok = True
        out.columns = result.columns
        out.rows = result.rows
        out.row_count = result.row_count
        out.duration_ms = result.duration_ms
        out.truncated = result.truncated
        return out

    # -- main -------------------------------------------------------------
    async def run(self, messages: list, ctx: UserContext) -> PipelineOutcome:
        settings = self.settings
        history, history_text, question = split_messages(messages)

        trace = RequestTrace(
            question=question,
            user=ctx.to_dict(),
            knobs=settings.ablation_knobs(),
            model=getattr(self.state.llm, "name", "unknown"),
        )

        # -- 1. retrieval --------------------------------------------------
        schema_text = self.state.schema_text_fallback
        with trace.stage("retrieval"):
            retrieval = self.state.retrieve(question)
        if retrieval is not None:
            schema_text = retrieval.prompt_text
            trace.retrieval = retrieval.to_dict()
        else:
            trace.retrieval = {"mode": "disabled", "tables": []}

        validator = self._validator(ctx)
        session = self._session(ctx)
        hidden = self._hidden_columns(ctx)

        prompt = llm_mod.build_sql_prompt(
            schema_text=schema_text,
            question=question,
            history_text=history_text,
            max_rows=validator.max_rows,
            hidden_columns=hidden,
            allow_clarification=settings.clarification_enabled,
        )

        sql_meta: dict = {
            "sql": None,
            "row_count": None,
            "duration_ms": None,
            "blocked": None,
            "request_id": trace.request_id,
            "role": ctx.role,
            "retrieval": {
                "mode": trace.retrieval.get("mode"),
                "tables": trace.retrieval.get("tables", []),
            },
        }

        chart_config: Optional[dict] = None
        result: Optional[QueryResult] = None
        outcome = OUTCOME_GENERATION_FAILED
        results_text: Optional[str] = None
        clarification: Optional[str] = None
        clarification_options: list[dict] = []
        last_error: Optional[str] = None

        max_attempts = max(1, settings.max_repair_attempts + 1)

        for attempt_index in range(max_attempts):
            # -- 2. generation --------------------------------------------
            with trace.stage("generation"):
                try:
                    payload = await asyncio.to_thread(
                        self.state.llm.generate_json, prompt
                    )
                except Exception as exc:
                    logger.error("SQL generation failed: %s", exc)
                    trace.add_attempt(
                        Attempt(
                            index=attempt_index,
                            stage="generation",
                            ok=False,
                            error=str(exc),
                        )
                    )
                    outcome = OUTCOME_GENERATION_FAILED
                    last_error = str(exc)
                    break

            sql = payload.get("sql")
            clarification = payload.get("clarification")
            clarification_options = _clean_options(payload.get("options"))
            chart_raw = payload.get("chart")
            if isinstance(chart_raw, dict) and chart_raw.get("type") not in (
                None,
                "none",
            ):
                chart_config = chart_raw

            if clarification and settings.clarification_enabled:
                trace.add_attempt(
                    Attempt(index=attempt_index, stage="generation", ok=True)
                )
                outcome = OUTCOME_CLARIFICATION
                trace.clarification = clarification
                break

            refusal = payload.get("refusal")
            if not sql and refusal:
                # The model recognised that the answer would need a column the
                # role cannot read. Same observable outcome as a policy block.
                reason = f"role '{ctx.role}' cannot read the data required: {refusal}"
                trace.add_attempt(
                    Attempt(
                        index=attempt_index,
                        stage="policy",
                        ok=False,
                        error=reason,
                    )
                )
                trace.policy = {"blocked_reason": reason, "role": ctx.role}
                outcome = OUTCOME_BLOCKED_POLICY
                last_error = reason
                break

            if not sql:
                trace.add_attempt(
                    Attempt(index=attempt_index, stage="generation", ok=True)
                )
                outcome = OUTCOME_NO_SQL
                break

            # -- 3. validation --------------------------------------------
            with trace.stage("validation"):
                validation = validator.validate(sql)
            if not validation.ok:
                logger.warning("SQL rejected by validator: %s", validation.error)
                trace.add_attempt(
                    Attempt(
                        index=attempt_index,
                        sql=sql,
                        stage="validation",
                        ok=False,
                        error=validation.error,
                    )
                )
                outcome = OUTCOME_VALIDATION_FAILED
                last_error = validation.error
                if attempt_index < max_attempts - 1:
                    prompt = llm_mod.build_repair_prompt(
                        schema_text,
                        question,
                        sql,
                        validation.error or "",
                        "validation",
                        validator.max_rows,
                    )
                    continue
                break

            safe_sql = validation.sql

            # -- 4. authorization -----------------------------------------
            if self.state.policy is not None and settings.policy_enabled:
                with trace.stage("policy"):
                    try:
                        policy_result = self.state.policy.rewrite(safe_sql, ctx)
                    except PolicyError as exc:
                        policy_result = None
                        last_error = str(exc)
                if policy_result is None or not policy_result.ok:
                    reason = (
                        policy_result.blocked_reason
                        if policy_result is not None
                        else last_error
                    )
                    logger.warning("blocked by policy: %s", reason)
                    trace.add_attempt(
                        Attempt(
                            index=attempt_index,
                            sql=safe_sql,
                            stage="policy",
                            ok=False,
                            error=reason,
                        )
                    )
                    trace.policy = {"blocked_reason": reason, "role": ctx.role}
                    outcome = OUTCOME_BLOCKED_POLICY
                    last_error = reason
                    break
                trace.policy = policy_result.to_dict()
                safe_sql = policy_result.sql

            # -- 5. dry run (EXPLAIN) --------------------------------------
            if settings.dry_run_enabled and self.state.can_explain:
                with trace.stage("dry_run"):
                    try:
                        await self.state.direct_runner.explain(safe_sql, session)
                        dry_error = None
                    except SqlExecutionError as exc:
                        dry_error = str(exc)
                if dry_error:
                    logger.info("dry run failed: %s", dry_error)
                    trace.add_attempt(
                        Attempt(
                            index=attempt_index,
                            sql=safe_sql,
                            stage="dry_run",
                            ok=False,
                            error=dry_error,
                        )
                    )
                    outcome = OUTCOME_EXECUTION_FAILED
                    last_error = dry_error
                    if attempt_index < max_attempts - 1:
                        prompt = llm_mod.build_repair_prompt(
                            schema_text,
                            question,
                            sql,
                            dry_error,
                            "EXPLAIN (dry run)",
                            validator.max_rows,
                        )
                        continue
                    break

            # -- 6. execution ---------------------------------------------
            with trace.stage("execution"):
                try:
                    result = await self.state.execute(safe_sql, session)
                    exec_error = None
                except SqlExecutionError as exc:
                    exec_error = str(exc)
                except Exception as exc:  # pragma: no cover - unexpected
                    exec_error = str(exc)

            if exec_error:
                logger.warning("SQL execution failed: %s", exec_error)
                trace.add_attempt(
                    Attempt(
                        index=attempt_index,
                        sql=safe_sql,
                        stage="execution",
                        ok=False,
                        error=exec_error,
                    )
                )
                outcome = OUTCOME_EXECUTION_FAILED
                last_error = exec_error
                if attempt_index < max_attempts - 1:
                    prompt = llm_mod.build_repair_prompt(
                        schema_text,
                        question,
                        sql,
                        exec_error,
                        "execution",
                        validator.max_rows,
                    )
                    continue
                break

            trace.add_attempt(
                Attempt(index=attempt_index, sql=safe_sql, stage="execution", ok=True)
            )
            trace.final_sql = safe_sql
            trace.row_count = result.row_count if result else 0
            results_text = format_results(result) if result else None
            sql_meta["sql"] = safe_sql
            sql_meta["row_count"] = result.row_count if result else 0
            sql_meta["duration_ms"] = result.duration_ms if result else 0.0
            outcome = OUTCOME_ANSWERED
            break

        # -- 7. assemble the response --------------------------------------
        trace.outcome = outcome
        trace.chart = chart_config
        sql_meta["outcome"] = outcome
        sql_meta["attempts"] = len(trace.attempts)
        sql_meta["retries"] = trace.retries

        sql_meta["model"] = getattr(self.state.llm, "name", "unknown")
        sql_meta["database"] = (
            self.state.catalog.database if self.state.catalog else None
        )
        sql_meta["max_rows"] = validator.max_rows
        sql_meta["truncated"] = bool(result.truncated) if result is not None else False
        sql_meta["stages"] = dict(trace.stages)
        sql_meta["total_ms"] = trace.total_ms
        # The whole attempt trail, not just how many there were: the repair loop
        # is only legible in the product if the failed attempt and its verbatim
        # database error travel with the answer.
        sql_meta["attempts_detail"] = [a.to_dict() for a in trace.attempts]

        # Retrieval: the ranked list, not only the tables that made the cut.
        sql_meta["retrieval"].update(
            {
                "ranking": trace.retrieval.get("ranking", []),
                "value_matches": trace.retrieval.get("value_matches", []),
                "expanded": trace.retrieval.get("expanded", []),
                "latency_ms": trace.retrieval.get("latency_ms"),
                "candidates": (
                    len(self.state.catalog.tables) if self.state.catalog else None
                ),
            }
        )

        # Authorization is always reported, so "no filter was needed" is
        # distinguishable from "the policy was never consulted".
        role_policy = self.state.policy.role(ctx.role) if self.state.policy else None
        sql_meta["policy"] = {
            "role": ctx.role,
            "enabled": bool(self.state.policy is not None and settings.policy_enabled),
            "filters": [f["table"] for f in trace.policy.get("applied_filters", [])],
            "filter_predicates": trace.policy.get("applied_filters", []),
            "expanded_stars": trace.policy.get("expanded_stars", []),
            "denied_columns": list(role_policy.denied_columns) if role_policy else [],
            "denied_tables": list(role_policy.denied_tables) if role_policy else [],
            "blocked_reason": trace.policy.get("blocked_reason"),
            "max_rows": validator.max_rows,
        }

        if outcome == OUTCOME_ANSWERED:
            answer_prompt = llm_mod.build_answer_prompt(question, results_text)
        elif outcome == OUTCOME_CLARIFICATION:
            sql_meta["clarification"] = clarification
            sql_meta["clarification_options"] = clarification_options
            answer_prompt = llm_mod.build_clarification_prompt(question, clarification or "")
        elif outcome == OUTCOME_NO_SQL:
            answer_prompt = llm_mod.build_answer_prompt(question, None)
        else:
            trace.error = last_error
            sql_meta["blocked"] = last_error
            sql_meta["sql"] = trace.attempts[-1].sql if trace.attempts else None
            note = {
                OUTCOME_BLOCKED_POLICY: (
                    "The request was refused by the access policy for role "
                    f"'{ctx.role}': {last_error}. Tell the user politely that they "
                    "are not authorised to see this data. Do not speculate about "
                    "the values."
                ),
                OUTCOME_VALIDATION_FAILED: (
                    f"The generated query could not be validated: {last_error}. "
                    "Tell the user the question could not be turned into a safe "
                    "query and suggest rephrasing."
                ),
                OUTCOME_EXECUTION_FAILED: (
                    f"The query failed to execute: {last_error}. Tell the user the "
                    "data could not be retrieved and suggest rephrasing."
                ),
                OUTCOME_GENERATION_FAILED: (
                    f"The language model could not produce a query ({last_error}). "
                    "Apologise briefly."
                ),
            }.get(outcome, "The request could not be completed.")
            answer_prompt = llm_mod.build_answer_prompt(question, note)

        data_payload = None
        if result is not None and result.columns:
            data_payload = {
                "columns": result.columns,
                "rows": result.rows,
                "chart": chart_config,
                "truncated": result.truncated,
                "row_count": result.row_count,
            }

        return PipelineOutcome(
            trace=trace,
            outcome=outcome,
            sql_meta=sql_meta,
            data_payload=data_payload,
            answer_prompt=answer_prompt,
            question=question,
            history=history,
            clarification=clarification,
        )
