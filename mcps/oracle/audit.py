import datetime
import json
import logging
import os
import time
from logging.handlers import RotatingFileHandler

import config

os.makedirs(os.path.dirname(config.AUDIT_LOG_PATH) or ".", exist_ok=True)

_logger = logging.getLogger("mcp_oracle_audit")
_logger.setLevel(logging.INFO)
_logger.propagate = False

if not _logger.handlers:
    _handler = RotatingFileHandler(
        config.AUDIT_LOG_PATH, maxBytes=10_000_000, backupCount=5, encoding="utf-8"
    )
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)


def log_query(
    tool: str,
    detail: str,
    max_rows: int | None,
    row_count: int | None,
    duration_ms: float,
    outcome: str,
) -> None:
    """Append one audit entry. `detail` is the SQL for run_query and a short
    target label (e.g. TABLE or TABLE.COLUMN) for the metadata tools."""
    now = time.time()
    entry = {
        "timestamp": now,
        "timestamp_iso": datetime.datetime.fromtimestamp(now, tz=datetime.timezone.utc).isoformat(),
        "tool": tool,
        "detail": detail,
        "max_rows": max_rows,
        "row_count": row_count,
        "duration_ms": round(duration_ms, 2),
        "outcome": outcome,
    }
    _logger.info(json.dumps(entry, default=str))
