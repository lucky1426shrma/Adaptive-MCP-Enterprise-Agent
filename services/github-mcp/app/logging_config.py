"""Structured logging configuration.

Identical in shape to the backend's logging config (see
`backend/app/logging_config.py`). Intentionally duplicated rather than
imported from a shared package: each MCP server must be independently
deployable (buildable/runnable/containerized on its own), and a runtime
cross-service import would work against that.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys

from app.log_redaction import SecretRedactionFilter
from app.log_correlation import TraceContextFilter
from datetime import datetime, timezone
from typing import Any, Dict

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)

_STANDARD_RECORD_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "request_id", "message", "taskName",
}


class RequestIdFilter(logging.Filter):
    """Attaches the current request's correlation ID to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """Renders each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_ATTRS:
                continue
            payload[key] = value

        return json.dumps(payload, default=str)


def configure_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Configure root logging for the process. Call once at startup."""
    root = logging.getLogger()
    root.setLevel(log_level.upper())

    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    # Phase 10: attaches the active OTel trace/span ID (no-op if
    # opentelemetry isn't installed or configured).
    handler.addFilter(TraceContextFilter())
    # Defense-in-depth: redacts any log field whose NAME looks secret-
    # like (e.g. this service's DATABASE_URL / GITHUB_TOKEN / AUTH_TOKEN),
    # even though the primary defense is simply never passing secrets
    # into `extra=` in the first place.
    handler.addFilter(SecretRedactionFilter())

    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | request_id=%(request_id)s | "
                "%(name)s | %(message)s"
            )
        )

    root.addHandler(handler)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
