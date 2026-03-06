import os
import json
import logging
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
SQL_BACKEND_URL = os.getenv("SQL_BACKEND_URL", "http://test_app_backend:8080")

app = FastAPI(title="RAG Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Schema context — baked in at startup
# ---------------------------------------------------------------------------
SCHEMA = """
Database: car_rental (PostgreSQL)

Tables:

locations(id, name, city, address, phone, created_at)
  - Branch offices. PK: id.

employees(id, location_id FK→locations, first_name, last_name,
          role CHECK('manager','agent','mechanic','receptionist'),
          salary NUMERIC, hire_date DATE, email, phone, created_at)

vehicle_categories(id, name UNIQUE, description, daily_rate_min NUMERIC, daily_rate_max NUMERIC)

vehicles(id, category_id FK→vehicle_categories, location_id FK→locations,
         make, model, year, license_plate UNIQUE, color, daily_rate NUMERIC,
         mileage INT, status CHECK('available','rented','maintenance','retired'), created_at)

clients(id, first_name, last_name, email UNIQUE, phone,
        drivers_license, date_of_birth DATE, registration_date DATE, created_at)

reservations(id, client_id FK→clients, vehicle_id FK→vehicles,
             pickup_location FK→locations, return_location FK→locations,
             pickup_date DATE, return_date DATE,
             status CHECK('confirmed','active','completed','cancelled','no_show'),
             total_cost NUMERIC, created_at)

payments(id, reservation_id FK→reservations, amount NUMERIC,
         payment_method CHECK('credit_card','debit_card','cash'),
         payment_date DATE,
         status CHECK('completed','pending','refunded','failed'), created_at)

maintenance_records(id, vehicle_id FK→vehicles,
                    maintenance_type CHECK('oil_change','tire_rotation','brake_service',
                      'general_inspection','engine_repair','body_repair',
                      'transmission','ac_service','battery_replacement'),
                    description TEXT, cost NUMERIC, maintenance_date DATE,
                    mileage_at_service INT, completed BOOL, created_at)

reviews(id, reservation_id FK→reservations, rating INT CHECK(1-5),
        comment TEXT, review_date DATE, created_at)
""".strip()

SQL_SYSTEM_PROMPT = f"""You are a SQL expert for a car rental company database.

{SCHEMA}

When given a user question, decide if it requires querying the database.

Respond ONLY with a valid JSON object — no markdown, no explanation, no extra text.

If the question needs data:
{{"sql": "SELECT ...", "reasoning": "one-line explanation"}}

If the question does NOT need data (e.g. greetings, general knowledge):
{{"sql": null, "reasoning": "no data needed"}}

Rules:
- Use only the tables and columns listed above.
- Always use table aliases for clarity in JOINs.
- Limit results to 100 rows unless the user asks for more.
- Never use DELETE, UPDATE, INSERT, DROP, or any DDL/DML except SELECT.
"""

ANSWER_SYSTEM_PROMPT = """You are a helpful assistant for a car rental company.
You have access to live data from the company database.
Answer the user's question naturally and concisely based on the data provided.
If the data is a table, summarise the key findings rather than listing every row unless asked.
Format numbers clearly (e.g. currency with 2 decimal places).
"""


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class MessageIn(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[MessageIn]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _configure_gemini():
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")
    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel(GEMINI_MODEL)


def _build_history(messages: list[MessageIn]) -> tuple[list[dict], str]:
    """Split messages into Gemini history + last user message."""
    history = []
    for msg in messages[:-1]:
        role = "model" if msg.role == "assistant" else "user"
        history.append({"role": role, "parts": [msg.content]})
    return history, messages[-1].content


async def _generate_sql(model, last_message: str) -> dict:
    """Turn 1: ask the model for SQL. Returns {sql, reasoning}."""
    chat = model.start_chat(history=[])
    # Prepend the system prompt as the very first user turn for models
    # that don't support a dedicated system role via start_chat.
    prompt = f"{SQL_SYSTEM_PROMPT}\n\nUser question: {last_message}"
    response = chat.send_message(prompt)
    raw = response.text.strip()

    # Strip markdown code fences if the model adds them despite instructions
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("SQL generation returned non-JSON: %s", raw)
        return {"sql": None, "reasoning": "parse error"}


async def _execute_sql(sql: str) -> dict:
    """Call the test_app_backend SQL runner."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{SQL_BACKEND_URL}/api/sql",
            json={"query": sql},
        )
        resp.raise_for_status()
        return resp.json()


def _format_results(sql_result: dict) -> str:
    """Render SQL results as a compact markdown table for the answer prompt."""
    columns = sql_result.get("columns", [])
    rows = sql_result.get("rows", [])
    row_count = sql_result.get("row_count", 0)
    duration_ms = sql_result.get("duration_ms", 0)

    if not columns:
        return f"Query returned no rows. ({duration_ms:.1f} ms)"

    header = " | ".join(columns)
    separator = " | ".join(["---"] * len(columns))
    body = "\n".join(" | ".join(str(cell) for cell in row) for row in rows)

    return (
        f"Query returned {row_count} row(s) in {duration_ms:.1f} ms:\n\n"
        f"| {header} |\n| {separator} |\n"
        + "\n".join(f"| {' | '.join(str(c) for c in row)} |" for row in rows)
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "model": GEMINI_MODEL}


@app.post("/chat")
async def chat(req: ChatRequest):
    if not req.messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    model = _configure_gemini()
    history, last_message = _build_history(req.messages)

    # -- Turn 1: SQL generation --
    sql_result_text = None
    sql_query = None
    try:
        sql_data = await _generate_sql(model, last_message)
        sql_query = sql_data.get("sql")
        logger.info("SQL decision — query: %s | reasoning: %s", sql_query, sql_data.get("reasoning"))
    except Exception as e:
        logger.error("SQL generation failed: %s", e)

    # -- Turn 2 (optional): execute SQL --
    if sql_query:
        try:
            result = await _execute_sql(sql_query)
            sql_result_text = _format_results(result)
            logger.info("SQL executed successfully — %d rows", result.get("row_count", 0))
        except Exception as e:
            logger.error("SQL execution failed: %s", e)
            sql_result_text = f"SQL execution error: {e}"

    # -- Turn 3: stream the final answer --
    if sql_result_text:
        answer_context = (
            f"The user asked: {last_message}\n\n"
            f"SQL run: `{sql_query}`\n\n"
            f"Results:\n{sql_result_text}"
        )
    else:
        answer_context = last_message

    answer_prompt = f"{ANSWER_SYSTEM_PROMPT}\n\n{answer_context}"

    answer_chat = model.start_chat(history=history)

    async def stream_response():
        try:
            response = answer_chat.send_message(answer_prompt, stream=True)
            for chunk in response:
                if chunk.text:
                    yield f"data: {chunk.text}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error("Gemini streaming error: %s", e)
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
