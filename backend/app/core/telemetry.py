"""OpenTelemetry initialisation (Milestone D4).

Enabled by setting ``OTEL_ENABLED=true`` in the environment.
When disabled (default) this module is a no-op; the app starts normally.

Environment variables
---------------------
OTEL_ENABLED                     — true | false (default: false)
OTEL_SERVICE_NAME                — service name tag (default: kotte-backend)
OTEL_EXPORTER_OTLP_ENDPOINT      — gRPC collector endpoint (default: http://localhost:4317)

Usage
-----
Call ``setup_telemetry(app)`` once from ``create_app()`` before adding
middleware.  FastAPI is auto-instrumented; the trace_id is plumbed into the
JSON log formatter so logs and traces link in Loki + Tempo.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


def setup_telemetry(app: "FastAPI") -> None:
    """Initialise OpenTelemetry SDK and auto-instrument FastAPI if enabled."""
    from app.core.config import settings

    if not settings.otel_enabled:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        resource = Resource(attributes={SERVICE_NAME: settings.otel_service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(app)
        logger.info(
            "OpenTelemetry enabled (service=%s, endpoint=%s)",
            settings.otel_service_name,
            settings.otel_exporter_otlp_endpoint,
        )
    except ImportError as exc:
        logger.warning("OpenTelemetry packages not installed; tracing disabled: %s", exc)
    except Exception as exc:
        logger.warning("OpenTelemetry setup failed; tracing disabled: %s", exc)


def get_trace_id() -> str | None:
    """Return the current span's trace ID as a hex string, or None."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.is_valid:
            return format(ctx.trace_id, "032x")
    except Exception:
        pass
    return None
