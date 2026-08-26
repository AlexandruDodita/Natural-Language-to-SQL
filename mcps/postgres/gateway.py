"""Small HTTP adapter for exposing the stdio MCP baseline to the demo UI.

The MCP server intentionally speaks stdio because that is the normal MCP
transport for a locally spawned server. Browsers cannot spawn a process, so
this adapter accepts one question over HTTP and runs the existing MCP client
harness unchanged. It is meant for the local Docker demo, not as a public API.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from client_harness import ask_async


HOST = os.environ.get("MCP_GATEWAY_HOST", "127.0.0.1")
PORT = int(os.environ.get("MCP_GATEWAY_PORT", "8300"))
MAX_BODY_BYTES = 32_000


def _number(value) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        return True
    try:
        float(str(value).replace(",", ""))
        return True
    except (TypeError, ValueError):
        return False


def _chart_for_result(question: str, columns: list[str], rows: list[list]) -> dict | None:
    """Choose a useful chart for the UI without changing the MCP baseline.

    The MCP comparison arm intentionally has no chart-generation prompt. This
    presentation-only inference lets the demo visualize ordinary category +
    numeric results while keeping MCP's SQL/tool-calling behavior unchanged.
    """
    if len(columns) < 2 or not rows:
        return None

    numeric_indices = [
        index for index in range(len(columns))
        if any(index < len(row) and _number(row[index]) for row in rows)
    ]
    label_indices = [
        index for index in range(len(columns))
        if index not in numeric_indices
    ]
    if not numeric_indices or not label_indices:
        return None

    question_lower = question.lower()
    if re.search(r"\b(month|monthly|trend|over time|evolution|evoluția)\b", question_lower):
        chart_type = "line"
    elif re.search(r"\b(pie|proportion|distribution|distribuția)\b", question_lower) and len(rows) <= 8:
        chart_type = "pie"
    else:
        chart_type = "bar"

    title = question.strip().rstrip("?.!")
    return {
        "type": chart_type,
        "title": title[:100] or "Query Results",
        "x": columns[label_indices[0]],
        "y": columns[numeric_indices[0]],
    }


class GatewayHandler(BaseHTTPRequestHandler):
    server_version = "postgres-mcp-gateway/1.0"

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self._send_json(204, {})

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "transport": "stdio"})
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path != "/ask":
            self._send_json(404, {"error": "not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0
        if content_length <= 0 or content_length > MAX_BODY_BYTES:
            self._send_json(400, {"error": "request body is missing or too large"})
            return

        try:
            payload = json.loads(self.rfile.read(content_length))
            question = payload.get("question", "")
        except (json.JSONDecodeError, AttributeError):
            self._send_json(400, {"error": "body must be JSON with a question"})
            return

        if not isinstance(question, str) or not question.strip():
            self._send_json(400, {"error": "question must be a non-empty string"})
            return

        try:
            result = asyncio.run(ask_async(question.strip()))
            response = result.to_dict()
            response["chart"] = _chart_for_result(
                question, response.get("columns", []), response.get("rows", [])
            )
            self._send_json(200, response)
        except Exception as exc:  # keep the browser-facing contract JSON
            self._send_json(502, {"error": str(exc)})

    def log_message(self, format: str, *args) -> None:
        # Keep MCP protocol output and gateway logs separate and concise.
        print(f"mcp-gateway: {format % args}", flush=True)


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), GatewayHandler)
    print(f"MCP gateway listening on {HOST}:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
