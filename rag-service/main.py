"""FastAPI layer for the RAG service.

Thin on purpose: request/response models, the SSE framing and a few
introspection endpoints. All the logic lives in the modules
(``schema_store``, ``retrieval``, ``validator``, ``policy``, ``pipeline``).

The SSE protocol is unchanged and only extended additively:
    data: [META]{...}   -- same keys as before, plus retrieval/policy/outcome
    data: [DATA]{...}   -- unchanged
    data: "text chunk"  -- unchanged (JSON encoded)
    data: [DONE]        -- unchanged
    data: [ERROR] msg   -- unchanged
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import threading
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import llm as llm_mod
from config import settings
from pipeline import Pipeline
from policy import UserContext
from report import ReportRequest, build_excel
from state import ServiceState
from telemetry import Telemetry
from validator import SqlValidator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

state = ServiceState(settings)
telemetry = Telemetry(settings.telemetry_path, settings.telemetry_enabled)
pipeline = Pipeline(settings, state, telemetry)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await state.initialize()
    except Exception as exc:  # never prevent the service from starting
        logger.exception("startup initialisation failed: %s", exc)
    yield


app = FastAPI(title="RAG Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class MessageIn(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class UserIn(BaseModel):
    """Minimal user context. Optional: when absent the server defaults apply,
    so the existing frontend keeps working without any change."""

    user_id: Optional[str] = None
    role: Optional[str] = None
    location_id: Optional[int] = None
    attributes: dict[str, Any] = {}


class ChatRequest(BaseModel):
    messages: list[MessageIn]
    user: Optional[UserIn] = None


class RetrieveRequest(BaseModel):
    question: str
    top_k: Optional[int] = None


class ValidateRequest(BaseModel):
    sql: str
    user: Optional[UserIn] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "model": settings.gemini_model, **state.status}


@app.get("/config")
async def config():
    return {"knobs": settings.ablation_knobs(), "settings": settings.public_dict()}


@app.get("/schema")
async def schema():
    if state.catalog is None:
        raise HTTPException(status_code=503, detail="schema catalog unavailable")
    return state.catalog.to_dict()


@app.post("/retrieve")
async def retrieve(req: RetrieveRequest):
    """Schema linking for one question — used to score retrieval recall."""
    result = state.retrieve(req.question, top_k=req.top_k)
    if result is None:
        raise HTTPException(status_code=503, detail="retrieval disabled or unavailable")
    return {**result.to_dict(), "prompt_text": result.prompt_text}


@app.post("/validate")
async def validate(req: ValidateRequest):
    """Dry validation + policy rewrite of a SQL string (no execution)."""
    ctx: UserContext = state.user_context(req.user.model_dump() if req.user else None)
    known = state.catalog.table_names if state.catalog else []
    validator = SqlValidator(
        dialect=settings.sql_dialect,
        max_rows=settings.max_rows,
        known_tables=known,
        enforce_known_tables=bool(known),
    )
    validation = validator.validate(req.sql)
    payload: dict = {"validation": validation.to_dict(), "sql": validation.sql}
    if validation.ok and state.policy is not None and settings.policy_enabled:
        policy_result = state.policy.rewrite(validation.sql, ctx)
        payload["policy"] = policy_result.to_dict()
        payload["sql"] = policy_result.sql if policy_result.ok else None
    return payload


@app.post("/admin/reindex")
async def reindex():
    return await state.rebuild_index()


@app.get("/telemetry/recent")
async def telemetry_recent(limit: int = 20):
    return {"records": telemetry.recent(limit)}


@app.get("/telemetry/summary")
async def telemetry_summary():
    return telemetry.summary()


@app.post("/chat")
async def chat(req: ChatRequest):
    if not req.messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    ctx = state.user_context(req.user.model_dump() if req.user else None)

    async def stream_response():
        trace = None
        try:
            # Kept inside the generator so that any unexpected failure is still
            # reported through the SSE protocol the frontend understands.
            outcome = await pipeline.run(req.messages, ctx)
            trace = outcome.trace
            yield f"data: [META]{json.dumps(outcome.sql_meta, default=str)}\n\n"
            if outcome.data_payload:
                yield f"data: [DATA]{json.dumps(outcome.data_payload, default=str)}\n\n"

            answered = False
            try:
                with trace.stage("answer"):
                    async for chunk in _stream_answer(
                        outcome.answer_prompt, outcome.history
                    ):
                        answered = True
                        yield f"data: {json.dumps(chunk)}\n\n"
            except Exception as exc:
                logger.error("answer streaming failed: %s", exc)
                if not answered:
                    fallback = _offline_answer(outcome)
                    trace.error = trace.error or str(exc)
                    yield f"data: {json.dumps(fallback)}\n\n"

            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.exception("streaming error: %s", exc)
            yield f"data: [ERROR] {str(exc)}\n\n"
        finally:
            if trace is not None:
                telemetry.record(trace)

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_answer(prompt: str, history: list[dict]):
    """Bridge the blocking LLM generator to async, chunk by chunk.

    Collecting the whole answer first would defeat the progressive rendering the
    frontend relies on, so chunks are pushed through a queue as they arrive.
    """
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def worker():
        try:
            for chunk in state.llm.stream_text(prompt, history):
                loop.call_soon_threadsafe(queue.put_nowait, ("chunk", chunk))
        except Exception as exc:
            loop.call_soon_threadsafe(queue.put_nowait, ("error", exc))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, ("done", None))

    threading.Thread(target=worker, daemon=True).start()

    while True:
        kind, value = await queue.get()
        if kind == "done":
            return
        if kind == "error":
            raise value
        yield value


def _offline_answer(outcome) -> str:
    """Last-resort textual answer when the LLM is unavailable.

    Keeps the SSE contract intact (the frontend always receives text) and makes
    the non-LLM stages demonstrable without an API key.
    """
    meta = outcome.sql_meta
    if outcome.clarification:
        return outcome.clarification
    if meta.get("blocked"):
        return f"Request refused: {meta['blocked']}"
    if meta.get("sql"):
        return (
            f"Query executed successfully and returned {meta.get('row_count', 0)} row(s). "
            "The natural-language summary is unavailable (language model offline)."
        )
    return "The language model is currently unavailable."


@app.post("/report")
async def generate_report(req: ReportRequest):
    try:
        excel_bytes = build_excel(req)
    except Exception as exc:
        logger.error("Excel generation failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    filename = f"{req.title or 'report'}.xlsx"
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
