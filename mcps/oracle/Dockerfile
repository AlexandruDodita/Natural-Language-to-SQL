FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY *.py ./
COPY scripts ./scripts

# Audit log destination (rotating). Mount a volume here to keep it across
# container restarts — it contains real query text, so treat it as sensitive.
RUN mkdir -p /app/logs
ENV AUDIT_LOG_PATH=/app/logs/audit.log

# No ORACLE_LIB_DIR is set, so python-oracledb stays in thin mode and needs
# no Oracle Instant Client. That is what keeps this image slim.
ENV MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

EXPOSE 8000

CMD ["python", "mcp_server.py"]
