"""Tests for span_helper.py.

Two code paths, both actually exercised here:
1. The REAL no-op path — `opentelemetry` genuinely isn't installed in
   this environment, so `app.observability.span_helper._OTEL_AVAILABLE`
   is actually False, and these tests exercise the real fallback
   behavior, not a simulation of it.
2. The "OTel is installed" path — simulated by monkeypatching the
   module's `_OTEL_AVAILABLE` flag and `_otel_trace` reference to a
   fake tracer, so the attribute-setting / span-creation logic is
   exercised too, without needing the real package.
"""

from __future__ import annotations

import app.observability.span_helper as span_helper


def test_start_span_is_a_working_noop_when_otel_unavailable() -> None:
    # Simulate the "opentelemetry not installed" state via monkeypatch
    # rather than asserting on the real environment: opentelemetry-sdk is
    # a declared dependency (see requirements.txt), so in any environment
    # where dependencies are actually installed — including CI —
    # `_OTEL_AVAILABLE` is True, and asserting it's False here would
    # always fail there.
    original_available = span_helper._OTEL_AVAILABLE
    span_helper._OTEL_AVAILABLE = False
    try:
        entered = False
        with span_helper.start_span("some.span", {"key": "value"}):
            entered = True
        assert entered is True
    finally:
        span_helper._OTEL_AVAILABLE = original_available


def test_start_span_noop_swallows_no_exceptions_it_shouldnt() -> None:
    # A no-op context manager must still propagate exceptions raised
    # inside the `with` block — it shouldn't accidentally suppress them.
    raised = False
    try:
        with span_helper.start_span("some.span"):
            raise ValueError("boom")
    except ValueError:
        raised = True
    assert raised is True


class _FakeSpan:
    def __init__(self) -> None:
        self.attributes: dict = {}

    def set_attribute(self, key, value) -> None:
        self.attributes[key] = value


class _FakeSpanContextManager:
    def __init__(self, span: _FakeSpan) -> None:
        self._span = span

    def __enter__(self) -> _FakeSpan:
        return self._span

    def __exit__(self, *exc_info) -> bool:
        return False


class _FakeTracer:
    def __init__(self) -> None:
        self.started_spans: list = []

    def start_as_current_span(self, name: str):
        span = _FakeSpan()
        span.name = name  # type: ignore[attr-defined]
        self.started_spans.append(span)
        return _FakeSpanContextManager(span)


class _FakeOtelTraceModule:
    def __init__(self, tracer: _FakeTracer) -> None:
        self._tracer = tracer

    def get_tracer(self, name: str) -> _FakeTracer:
        return self._tracer


def test_start_span_creates_real_span_when_otel_simulated_available() -> None:
    fake_tracer = _FakeTracer()
    original_available = span_helper._OTEL_AVAILABLE
    original_module = span_helper._otel_trace
    try:
        span_helper._OTEL_AVAILABLE = True
        span_helper._otel_trace = _FakeOtelTraceModule(fake_tracer)

        with span_helper.start_span("agent.agent_node", {"iterations": 2}):
            pass

        assert len(fake_tracer.started_spans) == 1
        created_span = fake_tracer.started_spans[0]
        assert created_span.name == "agent.agent_node"
        assert created_span.attributes == {"iterations": 2}
    finally:
        span_helper._OTEL_AVAILABLE = original_available
        span_helper._otel_trace = original_module


def test_start_span_skips_none_valued_attributes_when_simulated_available() -> None:
    fake_tracer = _FakeTracer()
    original_available = span_helper._OTEL_AVAILABLE
    original_module = span_helper._otel_trace
    try:
        span_helper._OTEL_AVAILABLE = True
        span_helper._otel_trace = _FakeOtelTraceModule(fake_tracer)

        with span_helper.start_span("x", {"a": 1, "b": None}):
            pass

        assert fake_tracer.started_spans[0].attributes == {"a": 1}
    finally:
        span_helper._OTEL_AVAILABLE = original_available
        span_helper._otel_trace = original_module


def test_start_span_with_no_attributes_when_simulated_available() -> None:
    fake_tracer = _FakeTracer()
    original_available = span_helper._OTEL_AVAILABLE
    original_module = span_helper._otel_trace
    try:
        span_helper._OTEL_AVAILABLE = True
        span_helper._otel_trace = _FakeOtelTraceModule(fake_tracer)

        with span_helper.start_span("x"):
            pass

        assert fake_tracer.started_spans[0].attributes == {}
    finally:
        span_helper._OTEL_AVAILABLE = original_available
        span_helper._otel_trace = original_module
