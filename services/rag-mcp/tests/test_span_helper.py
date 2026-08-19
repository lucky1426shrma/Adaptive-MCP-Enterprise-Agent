"""Two code paths, both actually exercised: the REAL no-op path
(opentelemetry genuinely isn't installed here), and a simulated
"installed" path via monkeypatching the module's globals."""

from __future__ import annotations

import app.span_helper as span_helper


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


def test_start_span_noop_propagates_exceptions() -> None:
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

        with span_helper.start_span("mcp.call_tool", {"tool": "search_knowledge"}):
            pass

        assert len(fake_tracer.started_spans) == 1
        assert fake_tracer.started_spans[0].name == "mcp.call_tool"
        assert fake_tracer.started_spans[0].attributes == {"tool": "search_knowledge"}
    finally:
        span_helper._OTEL_AVAILABLE = original_available
        span_helper._otel_trace = original_module
