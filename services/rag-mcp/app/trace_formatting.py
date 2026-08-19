"""Pure hex formatting for OpenTelemetry trace/span IDs.

OTel trace IDs are 128-bit integers, span IDs are 64-bit integers; the
W3C Trace Context spec (which OTel follows) represents them as
lowercase, fixed-width hex strings — 32 chars for a trace ID, 16 for a
span ID. This is just that integer-to-fixed-width-hex conversion, with
nothing OTel-specific in the implementation itself, which is what makes
it testable without the `opentelemetry` package installed.
"""

from __future__ import annotations


def format_trace_id(trace_id: int) -> str:
    return format(trace_id, "032x")


def format_span_id(span_id: int) -> str:
    return format(span_id, "016x")
