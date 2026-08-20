"""OpenTelemetry SDK setup: `TracerProvider` + `Resource` + an optional
OTLP exporter.

NOT MANDATORY, per the project spec: `OTEL_EXPORTER_OTLP_ENDPOINT`
unset means spans are still created everywhere `span_helper.start_span`
is called — real parent/child relationships, real attributes, real
durations — but never exported anywhere. That satisfies "no mandatory
paid/external observability dependency" while still exercising the
actual tracing code paths in every run, not just when someone bothers
to stand up a collector. Set `OTEL_EXPORTER_OTLP_ENDPOINT` to a
self-hosted OTLP collector (Jaeger, Tempo, an OTel Collector, etc.) —
never a requirement to run this project — to actually see traces.

VERSION CAVEAT: `opentelemetry-sdk`'s `TracerProvider` / `Resource` /
`BatchSpanProcessor` is core, stable, well-documented OTel API — lower
risk than, say, MCP SDK internals flagged elsewhere in this project —
but this could not be installed/run in the environment this was built
in (no network). Verify with `pip install -r requirements-dev.txt`
locally; if `configure_tracing` fails to import something, check the
installed `opentelemetry-sdk` version's docs first.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def configure_tracing(service_name: str, service_version: str, otlp_endpoint: Optional[str]) -> None:
    """Call once at process startup, before any spans are created."""
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning(
            "opentelemetry_not_installed",
            extra={"event": "opentelemetry_not_installed"},
        )
        return

    resource = Resource.create({"service.name": service_name, "service.version": service_version})
    provider = TracerProvider(resource=resource)

    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        except ImportError:
            logger.warning(
                "otlp_exporter_not_installed",
                extra={
                    "event": "otlp_exporter_not_installed",
                    "hint": "pip install opentelemetry-exporter-otlp-proto-http",
                },
            )
        else:
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info(
                "otlp_exporter_configured",
                extra={"event": "otlp_exporter_configured", "endpoint": otlp_endpoint},
            )
    else:
        logger.info(
            "tracing_configured_without_exporter",
            extra={
                "event": "tracing_configured_without_exporter",
                "note": "spans are created but not exported anywhere; set OTEL_EXPORTER_OTLP_ENDPOINT to change this",
            },
        )

    trace.set_tracer_provider(provider)
