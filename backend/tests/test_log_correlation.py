from __future__ import annotations

import logging

import app.observability.log_correlation as log_correlation
from app.observability.log_correlation import TraceContextFilter


def _make_record() -> logging.LogRecord:
    return logging.LogRecord(
        name="test", level=logging.INFO, pathname="x", lineno=1, msg="msg", args=(), exc_info=None
    )


def test_noop_when_otel_unavailable() -> None:
    # Simulate the "opentelemetry not installed" state via monkeypatch
    # rather than asserting on the real environment: opentelemetry-sdk is
    # a declared dependency (see requirements.txt), so in any environment
    # where dependencies are actually installed — including CI —
    # `_OTEL_AVAILABLE` is True, and the previous version of this test
    # (`assert log_correlation._OTEL_AVAILABLE is False`) would always
    # fail there.
    original_available = log_correlation._OTEL_AVAILABLE
    log_correlation._OTEL_AVAILABLE = False
    try:
        record = _make_record()
        result = TraceContextFilter().filter(record)

        assert result is True
        assert not hasattr(record, "trace_id")
        assert not hasattr(record, "span_id")
    finally:
        log_correlation._OTEL_AVAILABLE = original_available


class _FakeSpanContext:
    def __init__(self, is_valid: bool, trace_id: int = 0, span_id: int = 0) -> None:
        self.is_valid = is_valid
        self.trace_id = trace_id
        self.span_id = span_id


class _FakeSpan:
    def __init__(self, span_context: _FakeSpanContext) -> None:
        self._span_context = span_context

    def get_span_context(self) -> _FakeSpanContext:
        return self._span_context


class _FakeOtelTraceModule:
    def __init__(self, span: _FakeSpan) -> None:
        self._span = span

    def get_current_span(self) -> _FakeSpan:
        return self._span


def test_attaches_trace_and_span_id_when_valid_span_active() -> None:
    fake_span = _FakeSpan(_FakeSpanContext(is_valid=True, trace_id=255, span_id=15))
    original_available = log_correlation._OTEL_AVAILABLE
    original_module = log_correlation._otel_trace
    try:
        log_correlation._OTEL_AVAILABLE = True
        log_correlation._otel_trace = _FakeOtelTraceModule(fake_span)

        record = _make_record()
        TraceContextFilter().filter(record)

        assert record.trace_id == "0" * 30 + "ff"
        assert record.span_id == "0" * 15 + "f"
    finally:
        log_correlation._OTEL_AVAILABLE = original_available
        log_correlation._otel_trace = original_module


def test_does_not_attach_ids_when_span_context_invalid() -> None:
    fake_span = _FakeSpan(_FakeSpanContext(is_valid=False))
    original_available = log_correlation._OTEL_AVAILABLE
    original_module = log_correlation._otel_trace
    try:
        log_correlation._OTEL_AVAILABLE = True
        log_correlation._otel_trace = _FakeOtelTraceModule(fake_span)

        record = _make_record()
        TraceContextFilter().filter(record)

        assert not hasattr(record, "trace_id")
        assert not hasattr(record, "span_id")
    finally:
        log_correlation._OTEL_AVAILABLE = original_available
        log_correlation._otel_trace = original_module


def test_filter_always_returns_true() -> None:
    record = _make_record()
    assert TraceContextFilter().filter(record) is True
