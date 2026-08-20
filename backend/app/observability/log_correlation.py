"""Attaches the active OpenTelemetry trace/span ID to every log record,
so a structured log line can be pivoted to its corresponding trace in
whatever OTLP backend `OTEL_EXPORTER_OTLP_ENDPOINT` points at.

Gracefully does nothing if `opentelemetry` isn't installed, or if
there's no active span — this filter is always safe to attach to the
logging chain regardless of whether tracing is configured, mirroring
`app/security/log_redaction.py`'s "safe to always attach" design.
"""

from __future__ import annotations

import logging

from app.observability.trace_formatting import format_span_id, format_trace_id

try:
    from opentelemetry import trace as _otel_trace

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised by test monkeypatching instead
    _otel_trace = None  # type: ignore[assignment]
    _OTEL_AVAILABLE = False


class TraceContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not _OTEL_AVAILABLE:
            return True

        span = _otel_trace.get_current_span()
        span_context = span.get_span_context()
        if span_context.is_valid:
            record.trace_id = format_trace_id(span_context.trace_id)
            record.span_id = format_span_id(span_context.span_id)

        return True
