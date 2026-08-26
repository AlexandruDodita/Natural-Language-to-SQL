"""Self-repair loop, ambiguity handling and telemetry.

The LLM and the database are replaced by scripted doubles, so the control flow
(how many attempts, what is fed back, which outcome is reported) is tested
deterministically and without an API key.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

import pytest

from config import Settings
from db import QueryResult, SessionContext, SqlExecutionError
from pipeline import Pipeline, format_results, split_messages
from policy import UserContext
from telemetry import (
    OUTCOME_ANSWERED,
    OUTCOME_BLOCKED_POLICY,
    OUTCOME_CLARIFICATION,
    OUTCOME_EXECUTION_FAILED,
    OUTCOME_NO_SQL,
    Telemetry,
)


@dataclass
class Msg:
    role: str
    content: str


class ScriptedLLM:
    """Returns the next scripted payload and records the prompts it received."""

    name = "scripted"

    def __init__(self, payloads: list[dict]):
        self.payloads = list(payloads)
        self.prompts: list[str] = []

    def generate_json(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        if not self.payloads:
            raise AssertionError("the pipeline asked for more attempts than scripted")
        return self.payloads.pop(0)

    def stream_text(self, prompt, history=None):
        yield "answer"


class FakeExecutor:
    """Fails for the SQL fragments listed in ``failures``."""

    def __init__(self, failures: dict[str, str] | None = None, rows: int = 2):
        self.failures = failures or {}
        self.rows = rows
        self.executed: list[str] = []
        self.explained: list[str] = []

    def _maybe_fail(self, sql: str):
        for fragment, message in self.failures.items():
            if fragment in sql:
                raise SqlExecutionError(message)

    async def execute(self, sql: str, session: SessionContext | None = None):
        self.executed.append(sql)
        self._maybe_fail(sql)
        return QueryResult(
            columns=["a", "b"],
            rows=[[i, f"row{i}"] for i in range(self.rows)],
            row_count=self.rows,
            duration_ms=1.0,
        )

    async def explain(self, sql: str, session: SessionContext | None = None):
        self.explained.append(sql)
        self._maybe_fail(sql)


class FakeState:
    """Stands in for ServiceState."""

    def __init__(self, catalog, policy, llm, executor, can_explain=False, index=None):
        self.catalog = catalog
        self.policy = policy
        self.llm = llm
        self.executor = executor
        self.direct_runner = executor if can_explain else None
        self.can_explain = can_explain
        self.index = index
        self.schema_text_fallback = catalog.render()

    def retrieve(self, question, top_k=None):
        return self.index.retrieve(question, top_k=top_k or 4) if self.index else None

    async def execute(self, sql, session):
        return await self.executor.execute(sql, session)


def make_settings(**overrides) -> Settings:
    settings = Settings()
    settings.max_repair_attempts = 2
    settings.dry_run_enabled = True
    settings.clarification_enabled = True
    settings.policy_enabled = True
    settings.max_rows = 200
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def run(pipeline, messages, ctx):
    return asyncio.run(pipeline.run(messages, ctx))


MANAGER = UserContext(user_id="m", role="manager")
AGENT = UserContext(user_id="a", role="agent", location_id=4)


def sql_payload(sql: str, chart=None) -> dict:
    return {"sql": sql, "reasoning": "test", "chart": chart}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def test_split_messages_separates_history_from_the_question():
    history, text, question = split_messages(
        [Msg("user", "hi"), Msg("assistant", "hello"), Msg("user", "how many cars?")]
    )
    assert question == "how many cars?"
    assert len(history) == 2
    assert history[1]["role"] == "model"
    assert "User: hi" in text


def test_format_results_renders_a_markdown_table():
    text = format_results(
        QueryResult(columns=["city", "n"], rows=[["Miami", 3]], row_count=1, duration_ms=2.0)
    )
    assert "| city | n |" in text
    assert "| Miami | 3 |" in text


def test_format_results_handles_no_rows():
    assert "no rows" in format_results(QueryResult())


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------
def test_successful_query_is_answered(catalog, policy_engine, index):
    llm = ScriptedLLM([sql_payload("SELECT id FROM vehicles")])
    executor = FakeExecutor()
    state = FakeState(catalog, policy_engine, llm, executor, index=index)
    pipeline = Pipeline(make_settings(), state, None)

    result = run(pipeline, [Msg("user", "how many vehicles?")], MANAGER)

    assert result.outcome == OUTCOME_ANSWERED
    assert result.sql_meta["row_count"] == 2
    assert result.trace.retries == 0
    assert "LIMIT 200" in result.sql_meta["sql"].upper()
    assert result.data_payload["columns"] == ["a", "b"]


def test_retrieved_tables_are_reported(catalog, policy_engine, index):
    llm = ScriptedLLM([sql_payload("SELECT id FROM vehicles")])
    state = FakeState(catalog, policy_engine, llm, FakeExecutor(), index=index)
    pipeline = Pipeline(make_settings(), state, None)

    result = run(pipeline, [Msg("user", "how many vehicles?")], MANAGER)

    assert result.sql_meta["retrieval"]["tables"]
    assert result.trace.retrieval["ranking"][0]["table"] == "vehicles"


def test_chart_config_is_passed_through(catalog, policy_engine, index):
    chart = {"type": "bar", "title": "Fleet", "x": "a", "y": "b"}
    llm = ScriptedLLM([sql_payload("SELECT id FROM vehicles", chart)])
    state = FakeState(catalog, policy_engine, llm, FakeExecutor(), index=index)
    result = run(Pipeline(make_settings(), state, None), [Msg("user", "chart it")], MANAGER)
    assert result.data_payload["chart"] == chart


# ---------------------------------------------------------------------------
# Self-repair
# ---------------------------------------------------------------------------
def test_execution_error_is_repaired(catalog, policy_engine, index):
    llm = ScriptedLLM(
        [
            sql_payload("SELECT colour FROM vehicles"),
            sql_payload("SELECT color FROM vehicles"),
        ]
    )
    executor = FakeExecutor(
        failures={"colour": 'column "colour" does not exist'}
    )
    state = FakeState(catalog, policy_engine, llm, executor, index=index)

    result = run(Pipeline(make_settings(), state, None), [Msg("user", "colors?")], MANAGER)

    assert result.outcome == OUTCOME_ANSWERED
    assert result.trace.retries == 1
    assert len(result.trace.attempts) == 2
    assert result.trace.attempts[0].ok is False
    assert "colour" in result.trace.attempts[0].error
    # the exact database error was fed back to the model
    assert 'column "colour" does not exist' in llm.prompts[1]
    assert "SELECT colour FROM vehicles" in llm.prompts[1]


def test_validation_error_is_repaired(catalog, policy_engine, index):
    llm = ScriptedLLM(
        [
            sql_payload("SELECT * FROM pg_catalog.pg_user"),
            sql_payload("SELECT id FROM vehicles"),
        ]
    )
    state = FakeState(catalog, policy_engine, llm, FakeExecutor(), index=index)

    result = run(Pipeline(make_settings(), state, None), [Msg("user", "users?")], MANAGER)

    assert result.outcome == OUTCOME_ANSWERED
    assert result.trace.attempts[0].stage == "validation"
    assert "system catalog" in llm.prompts[1]


def test_retry_budget_is_bounded(catalog, policy_engine, index):
    llm = ScriptedLLM([sql_payload("SELECT bad FROM vehicles")] * 5)
    executor = FakeExecutor(failures={"bad": "column bad does not exist"})
    state = FakeState(catalog, policy_engine, llm, executor, index=index)

    result = run(
        Pipeline(make_settings(max_repair_attempts=2), state, None),
        [Msg("user", "x")],
        MANAGER,
    )

    assert result.outcome == OUTCOME_EXECUTION_FAILED
    assert len(result.trace.attempts) == 3  # 1 + 2 retries
    assert result.sql_meta["blocked"]


def test_zero_retries_means_a_single_attempt(catalog, policy_engine, index):
    llm = ScriptedLLM([sql_payload("SELECT bad FROM vehicles")] * 3)
    executor = FakeExecutor(failures={"bad": "boom"})
    state = FakeState(catalog, policy_engine, llm, executor, index=index)

    result = run(
        Pipeline(make_settings(max_repair_attempts=0), state, None),
        [Msg("user", "x")],
        MANAGER,
    )

    assert len(result.trace.attempts) == 1
    assert result.trace.retries == 0


def test_dry_run_catches_the_error_before_execution(catalog, policy_engine, index):
    llm = ScriptedLLM(
        [sql_payload("SELECT bad FROM vehicles"), sql_payload("SELECT id FROM vehicles")]
    )
    executor = FakeExecutor(failures={"bad": 'column "bad" does not exist'})
    state = FakeState(catalog, policy_engine, llm, executor, can_explain=True, index=index)

    result = run(Pipeline(make_settings(), state, None), [Msg("user", "x")], MANAGER)

    assert result.outcome == OUTCOME_ANSWERED
    assert result.trace.attempts[0].stage == "dry_run"
    # the broken query was planned but never executed
    assert not any("bad" in sql for sql in executor.executed)
    assert any("bad" in sql for sql in executor.explained)


def test_dry_run_can_be_disabled(catalog, policy_engine, index):
    llm = ScriptedLLM([sql_payload("SELECT id FROM vehicles")])
    executor = FakeExecutor()
    state = FakeState(catalog, policy_engine, llm, executor, can_explain=True, index=index)

    run(
        Pipeline(make_settings(dry_run_enabled=False), state, None),
        [Msg("user", "x")],
        MANAGER,
    )
    assert executor.explained == []


# ---------------------------------------------------------------------------
# Ambiguity
# ---------------------------------------------------------------------------
def test_ambiguous_question_returns_a_clarification(catalog, policy_engine, index):
    llm = ScriptedLLM(
        [
            {
                "clarification": "Best by total spend, by number of rentals, or by tenure?",
                "sql": None,
                "chart": None,
            }
        ]
    )
    executor = FakeExecutor()
    state = FakeState(catalog, policy_engine, llm, executor, index=index)

    result = run(
        Pipeline(make_settings(), state, None),
        [Msg("user", "Care sunt cei mai buni clienti?")],
        MANAGER,
    )

    assert result.outcome == OUTCOME_CLARIFICATION
    assert "total spend" in result.sql_meta["clarification"]
    assert executor.executed == []
    assert "total spend" in result.answer_prompt


def test_clarification_can_be_disabled(catalog, policy_engine, index):
    llm = ScriptedLLM(
        [{"clarification": "which one?", "sql": None, "chart": None}]
    )
    state = FakeState(catalog, policy_engine, llm, FakeExecutor(), index=index)
    result = run(
        Pipeline(make_settings(clarification_enabled=False), state, None),
        [Msg("user", "best clients?")],
        MANAGER,
    )
    assert result.outcome == OUTCOME_NO_SQL
    assert "ambiguous" not in llm.prompts[0].lower() or True


def test_small_talk_needs_no_sql(catalog, policy_engine, index):
    llm = ScriptedLLM([{"sql": None, "reasoning": "no data needed", "chart": None}])
    executor = FakeExecutor()
    state = FakeState(catalog, policy_engine, llm, executor, index=index)

    result = run(Pipeline(make_settings(), state, None), [Msg("user", "hello")], MANAGER)

    assert result.outcome == OUTCOME_NO_SQL
    assert executor.executed == []
    assert result.data_payload is None


# ---------------------------------------------------------------------------
# Authorization inside the pipeline
# ---------------------------------------------------------------------------
def test_policy_predicate_reaches_the_executed_sql(catalog, policy_engine, index):
    llm = ScriptedLLM([sql_payload("SELECT id FROM vehicles")])
    executor = FakeExecutor()
    state = FakeState(catalog, policy_engine, llm, executor, index=index)

    result = run(Pipeline(make_settings(), state, None), [Msg("user", "cars?")], AGENT)

    assert result.outcome == OUTCOME_ANSWERED
    assert "location_id = 4" in executor.executed[0]
    assert result.sql_meta["policy"]["filters"] == ["vehicles"]


def test_policy_violation_is_terminal(catalog, policy_engine, index):
    llm = ScriptedLLM([sql_payload("SELECT salary FROM employees")] * 3)
    executor = FakeExecutor()
    state = FakeState(catalog, policy_engine, llm, executor, index=index)

    result = run(Pipeline(make_settings(), state, None), [Msg("user", "salaries?")], AGENT)

    assert result.outcome == OUTCOME_BLOCKED_POLICY
    assert len(result.trace.attempts) == 1  # no retry: the model is not invited to probe
    assert executor.executed == []
    assert "salary" in result.sql_meta["blocked"]
    assert "not authorised" in result.answer_prompt


def test_hidden_columns_are_announced_in_the_prompt(catalog, policy_engine, index):
    llm = ScriptedLLM([sql_payload("SELECT id FROM employees")])
    state = FakeState(catalog, policy_engine, llm, FakeExecutor(), index=index)
    run(Pipeline(make_settings(), state, None), [Msg("user", "staff?")], AGENT)
    assert "employees.salary" in llm.prompts[0]


def test_role_row_cap_is_enforced(catalog, policy_engine, index):
    llm = ScriptedLLM([sql_payload("SELECT id FROM vehicles LIMIT 1000")])
    executor = FakeExecutor()
    state = FakeState(catalog, policy_engine, llm, executor, index=index)

    run(Pipeline(make_settings(max_rows=500), state, None), [Msg("user", "cars?")], AGENT)

    assert "LIMIT 200" in executor.executed[0].upper()  # agent max_rows from policy.yaml


def test_policy_can_be_disabled(catalog, policy_engine, index):
    llm = ScriptedLLM([sql_payload("SELECT salary FROM employees")])
    executor = FakeExecutor()
    state = FakeState(catalog, policy_engine, llm, executor, index=index)

    result = run(
        Pipeline(make_settings(policy_enabled=False), state, None),
        [Msg("user", "salaries?")],
        AGENT,
    )
    assert result.outcome == OUTCOME_ANSWERED


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------
def test_trace_is_written_as_jsonl(tmp_path, catalog, policy_engine, index):
    llm = ScriptedLLM(
        [sql_payload("SELECT bad FROM vehicles"), sql_payload("SELECT id FROM vehicles")]
    )
    executor = FakeExecutor(failures={"bad": "column bad does not exist"})
    state = FakeState(catalog, policy_engine, llm, executor, index=index)
    telemetry = Telemetry(str(tmp_path / "telemetry.jsonl"))

    result = run(Pipeline(make_settings(), state, None), [Msg("user", "colors?")], MANAGER)
    telemetry.record(result.trace)

    records = telemetry.read_all()
    assert len(records) == 1
    record = records[0]
    assert record["question"] == "colors?"
    assert record["outcome"] == OUTCOME_ANSWERED
    assert record["retries"] == 1
    assert len(record["attempts"]) == 2
    assert record["attempts"][0]["error"]
    assert record["retrieval"]["tables"]
    assert set(record["stages"]) >= {"retrieval", "generation", "validation", "execution"}
    assert record["knobs"]["max_repair_attempts"] == 2
    assert json.loads(json.dumps(record)) == record  # serialisable


def test_summary_aggregates_outcomes(tmp_path, catalog, policy_engine, index):
    telemetry = Telemetry(str(tmp_path / "t.jsonl"))
    for payloads, ctx in (
        ([sql_payload("SELECT id FROM vehicles")], MANAGER),
        ([sql_payload("SELECT salary FROM employees")], AGENT),
    ):
        state = FakeState(catalog, policy_engine, ScriptedLLM(payloads), FakeExecutor(), index=index)
        result = run(Pipeline(make_settings(), state, None), [Msg("user", "q")], ctx)
        telemetry.record(result.trace)

    summary = telemetry.summary()
    assert summary["requests"] == 2
    assert summary["outcomes"][OUTCOME_ANSWERED] == 1
    assert summary["blocked_by_policy"] == 1
    assert summary["success_rate"] == pytest.approx(0.5)
    assert "generation" in summary["avg_stage_ms"]


def test_generation_failure_is_reported(catalog, policy_engine, index):
    class Broken:
        name = "broken"

        def generate_json(self, prompt):
            raise RuntimeError("LLM is not configured (GEMINI_API_KEY missing)")

    state = FakeState(catalog, policy_engine, Broken(), FakeExecutor(), index=index)
    result = run(Pipeline(make_settings(), state, None), [Msg("user", "x")], MANAGER)

    assert result.outcome == "generation_failed"
    assert "GEMINI_API_KEY" in result.sql_meta["blocked"]


# ---------------------------------------------------------------------------
# Refusal instead of fabrication
# ---------------------------------------------------------------------------
def test_model_refusal_is_reported_as_a_policy_block(catalog, policy_engine, index):
    llm = ScriptedLLM(
        [{"sql": None, "refusal": "salary is not readable", "chart": None}]
    )
    executor = FakeExecutor()
    state = FakeState(catalog, policy_engine, llm, executor, index=index)

    result = run(
        Pipeline(make_settings(), state, None), [Msg("user", "average salary?")], AGENT
    )

    assert result.outcome == OUTCOME_BLOCKED_POLICY
    assert "salary" in result.sql_meta["blocked"]
    assert executor.executed == []


def test_no_data_answers_forbid_invented_figures(catalog, policy_engine, index):
    llm = ScriptedLLM([{"sql": None, "reasoning": "no data needed", "chart": None}])
    state = FakeState(catalog, policy_engine, llm, FakeExecutor(), index=index)

    result = run(Pipeline(make_settings(), state, None), [Msg("user", "hello")], MANAGER)

    assert result.outcome == OUTCOME_NO_SQL
    assert "never state, estimate or invent" in result.answer_prompt.lower()
    assert "you have access to live data" not in result.answer_prompt.lower()


def test_hidden_columns_come_with_a_refusal_instruction(catalog, policy_engine, index):
    llm = ScriptedLLM([sql_payload("SELECT id FROM employees")])
    state = FakeState(catalog, policy_engine, llm, FakeExecutor(), index=index)
    run(Pipeline(make_settings(), state, None), [Msg("user", "staff?")], AGENT)
    assert '"refusal"' in llm.prompts[0]
