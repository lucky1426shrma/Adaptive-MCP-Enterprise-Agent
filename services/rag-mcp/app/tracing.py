"""OpenTelemetry SDK setup: `TracerProvider` + `Resource` + an optional
OTLP exporter.

NOT MANDATORY: `OTEL_EXPORTER_OTLP_ENDPOINT` unset means spans are
still created (visible to any `span_helper.start_span()` caller) but
never exported anywhere — satisfies "no mandatory external
observability dependency" while still exercising real tracing code
paths. Set `OTEL_EXPORTER_OTLP_ENDPOINT` to a self-hosted OTLP
collector to actually see traces; never a requirement to run this
service.

VERSION CAVEAT: this couldn't be installed/run in the environment this
was built in (no network) — the core SDK API used here is stable, but
verify locally.
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
        logger.warning("opentelemetry_not_installed", extra={"event": "opentelemetry_not_installed"})
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
            extra={"event": "tracing_configured_without_exporter"},
        )

    trace.set_tracer_provider(provider)
