"""Optional-dependency span helper.

If `opentelemetry` isn't installed, `start_span()` is a no-op context
manager. This lets tracing instrumentation reach any module —
including ones with no other reason to depend on `opentelemetry` —
without adding a hard dependency: callers can call `start_span(...)`
unconditionally, and whether it does anything real depends entirely on
this module's import-time detection.

When `opentelemetry` IS installed and a `TracerProvider` has been
configured (see `tracing.py`, called once at service startup), real
spans are created and nested correctly under whatever span is active.
"""

from __future__ import annotations

import contextlib
from typing import Any, Dict, Iterator, Optional

try:
    from opentelemetry import trace as _otel_trace

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised by test monkeypatching instead
    _otel_trace = None  # type: ignore[assignment]
    _OTEL_AVAILABLE = False

_TRACER_NAME = "adaptive-mcp-enterprise-agent"


@contextlib.contextmanager
def start_span(name: str, attributes: Optional[Dict[str, Any]] = None) -> Iterator[None]:
    """Start a span named `name` for the duration of the `with` block.

    No-op if `opentelemetry` isn't installed. `None`-valued attributes
    are skipped rather than passed through — OTel span attributes must
    be a fixed set of primitive types, and `None` isn't one of them.
    """
    if not _OTEL_AVAILABLE:
        yield
        return

    tracer = _otel_trace.get_tracer(_TRACER_NAME)
    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                if value is not None:
                    span.set_attribute(key, value)
        yield
