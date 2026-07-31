"""
Logging and request correlation.

The application printed to stdout — 294 calls, many with emoji — which is
readable when you are watching one terminal and useless the moment something
fails in production. A print has no level, so nothing can be filtered; no
timestamp, so nothing can be correlated; and no request context, so a failure
cannot be tied to the call that caused it.

Set LOG_FORMAT=json for a log aggregator, or leave it as text for a terminal.
"""
from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any, Dict

# Set per request and read by the formatter, so every line emitted while
# handling a request carries its id without any call site passing it along.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# Chatty third parties that would otherwise bury our own output.
NOISY_LOGGERS = ("httpx", "httpcore", "urllib3", "asyncio", "multipart")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class TextFormatter(logging.Formatter):
    """Human-readable, with the request id when there is one."""

    def format(self, record: logging.LogRecord) -> str:
        rid = getattr(record, "request_id", "-")
        prefix = f"[{rid[:8]}] " if rid and rid != "-" else ""
        base = super().format(record)
        return f"{prefix}{base}"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Anything attached via logger.info(..., extra={...}).
        for key, value in record.__dict__.items():
            if key.startswith("ctx_"):
                payload[key[4:]] = value
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO", fmt: str = "text") -> None:
    """Install handlers. Safe to call more than once."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(
        JsonFormatter()
        if fmt.lower() == "json"
        else TextFormatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s",
                           datefmt="%H:%M:%S")
    )

    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def new_request_id() -> str:
    return uuid.uuid4().hex


def bind_request_id(request_id: str):
    """Bind an id for the current context; returns the token to reset with."""
    return request_id_var.set(request_id)
