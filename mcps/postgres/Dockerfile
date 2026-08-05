FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY db.py server.py llm_gemini.py client_harness.py ./

# Defaults; override at `docker run`/compose time. See .env.example.
ENV DATABASE_URL=postgresql://readonly_user:readonly_pass@test_app_db:5432/car_rental \
    MAX_ROWS=100 \
    STATEMENT_TIMEOUT_MS=5000

# MCP communicates over stdio, not a network port — this image is meant to
# be run with `docker run -i ...` (or exec'd into) by an MCP client, not
# exposed as a network service. No EXPOSE / CMD host binding needed.
ENTRYPOINT ["python", "server.py"]
