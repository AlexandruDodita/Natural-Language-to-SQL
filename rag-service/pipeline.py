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

        if trace.policy:
            sql_meta["policy"] = {
                "role": ctx.role,
                "filters": [f["table"] for f in trace.policy.get("applied_filters", [])],
                "blocked_reason": trace.policy.get("blocked_reason"),
            }

        if outcome == OUTCOME_ANSWERED:
            answer_prompt = llm_mod.build_answer_prompt(question, results_text)
        elif outcome == OUTCOME_CLARIFICATION:
            sql_meta["clarification"] = clarification
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
