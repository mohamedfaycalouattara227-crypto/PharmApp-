"""Formatter JSON pour logs de production — compatible SIEM (ELK, Loki, Splunk)."""
import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    _RESERVED = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "asctime",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
            "request_id": getattr(record, "request_id", "-"),
        }
        # Champs custom
        for k, v in record.__dict__.items():
            if k not in self._RESERVED and k not in payload:
                try:
                    json.dumps(v)
                    payload[k] = v
                except TypeError:
                    payload[k] = str(v)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)
