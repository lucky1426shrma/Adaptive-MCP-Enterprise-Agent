"""Structured logging configuration.

Production code in this project logs structured JSON events rather than
using `print` or unstructured log strings, so logs are consumable by log
aggregation tooling and (in the observability phase) correlate cleanly
with OpenTelemetry traces via `request_id`.

Every log record automatically carries the current request's correlation
ID via `request_id_var`, which `app.middleware.RequestContextMiddleware`
populates per request.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from app.observability.log_correlation import TraceContextFilter
from app.security.log_redaction import SecretRedactionFilter

# Populated per-request by RequestContextMiddleware. Defaults to "-" for
# log lines emitted outside of a request context (e.g. at startup).
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)

# Standard LogRecord attributes we don't want to re-emit as top-level JSON
# fields (they're either already represented, e.g. `message`, or are
# internal bookkeeping, e.g. `stack_info`).
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
    """Renders each log record as a single-line JSON object.

    Structured extras passed via `logger.info(..., extra={"event": ...})`
    are merged into the top-level JSON payload, matching the event-style
    logging convention used throughout this project (see
    `app/middleware.py` for examples).
    """

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
    """Configure root logging for the process. Call once at startup.

    Args:
        log_level: e.g. "DEBUG", "INFO", "WARNING".
        log_format: "json" for structured logs (default, recommended for
            anything other than local scratch debugging), or "console"
            for a human-readable single-line format.
    """
    root = logging.getLogger()
    root.setLevel(log_level.upper())

    # Avoid duplicate handlers if configure_logging is called more than
    # once in the same process (e.g. across tests).
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    # Phase 10: attaches the active OTel trace/span ID (no-op if
    # opentelemetry isn't installed or configured) so a log line can be
    # pivoted to its trace in whatever OTLP backend is configured.
    handler.addFilter(TraceContextFilter())
    # Defense-in-depth: redacts any log field whose NAME looks secret-
    # like, even though the primary defense is simply never passing
    # secrets into `extra=` in the first place (see log_redaction.py's
    # docstring for the exact scope/limitation).
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

    # uvicorn's access log duplicates what RequestContextMiddleware already
    # logs as structured `request_completed` events; keep it quiet by
    # default to avoid noisy, unstructured duplicate lines.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
