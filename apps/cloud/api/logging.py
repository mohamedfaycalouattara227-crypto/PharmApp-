"""
api/logging.py
Formateur JSON et filtre Request-ID pour les logs du Cloud PharmApp.
"""

import json
import logging
import traceback
from datetime import datetime, timezone

from api.middleware import get_request_id


class FiltreRequestId(logging.Filter):
    """Injecte request_id dans chaque LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class FormateurJson(logging.Formatter):
    """
    Formateur JSON structuré pour exploitation SIEM.
    Chaque ligne de log est un objet JSON valide.
    """

    def format(self, record: logging.LogRecord) -> str:
        entree: dict = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "niveau":    record.levelname,
            "logger":    record.name,
            "message":   record.getMessage(),
            "request_id": getattr(record, "request_id", ""),
            "module":    record.module,
            "line":      record.lineno,
        }

        # Champs extra injectés via logger.xxx(msg, extra={...})
        for cle, valeur in record.__dict__.items():
            if cle not in {
                "args", "created", "exc_info", "exc_text", "filename",
                "funcName", "levelname", "levelno", "lineno", "message",
                "module", "msecs", "msg", "name", "pathname", "process",
                "processName", "relativeCreated", "stack_info", "thread",
                "threadName", "request_id",
            }:
                entree[cle] = valeur

        # Exception
        if record.exc_info:
            entree["exception"] = self.formatException(record.exc_info)

        return json.dumps(entree, ensure_ascii=False, default=str)
