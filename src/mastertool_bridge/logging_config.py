"""Logging estruturado da camada externa."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class JsonLineFormatter(logging.Formatter):
    """Uma linha JSON por registro, com campos padronizados do projeto."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
            "level": record.levelname,
            "script": record.name,
            "message": record.getMessage(),
            "read_only": True,
        }
        for field in ("operation", "project", "object", "result",
                      "error", "duration_ms"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO", json_output: bool = False) -> logging.Logger:
    logger = logging.getLogger("mastertool_bridge")
    logger.setLevel(level.upper())
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        if json_output:
            handler.setFormatter(JsonLineFormatter())
        else:
            handler.setFormatter(
                logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.propagate = False
    return logger
