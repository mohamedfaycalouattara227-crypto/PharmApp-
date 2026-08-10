"""api/logging.py — Formateur JSON pour logs structurés en production."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Log JSON compatible ingest ELK / Loki / Datadog."""

    RESERVED = {
        "args", "asctime", "created", "exc_info", "exc_text", "filename",
        "funcName", "levelname", "levelno", "lineno", "module",
        "msecs", "message", "msg", "name", "pathname", "process",
        "processName", "relativeCreated", "stack_info", "thread", "threadName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "niveau": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "ligne": record.lineno,
            "request_id": getattr(record, "request_id", "-"),
        }
        # Champs libres passés via `extra={...}`
        for key, value in record.__dict__.items():
            if key not in self.RESERVED and key not in payload and not key.startswith("_"):
                try:
                    json.dumps(value)
                    payload[key] = value
                except (TypeError, ValueError):
                    payload[key] = repr(value)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)
