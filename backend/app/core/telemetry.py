"""Optional OpenTelemetry tracing (OTLP/HTTP).

Enabled when OTEL_EXPORTER_OTLP_ENDPOINT is set and the opentelemetry
packages are installed. Works with the AWS Distro for OpenTelemetry
collector (CloudWatch/X-Ray), the Datadog Agent OTLP intake and Grafana
Alloy/Tempo; standard OTEL_* variables configure headers and sampling.
"""
import logging
import os

logger = logging.getLogger(__name__)


def init_tracing(app) -> bool:
    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning("otel_packages_missing; tracing disabled")
        return False
    resource = Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", "baalebos-api"),
                                "deployment.environment": os.getenv("ENVIRONMENT", "production")})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    # Query strings and request bodies are not recorded as span attributes.
    FastAPIInstrumentor.instrument_app(app, excluded_urls="health,metrics", tracer_provider=provider)
    from backend.app.database import engine, read_engine
    SQLAlchemyInstrumentor().instrument(engines=[e for e in {engine, read_engine}], tracer_provider=provider)
    logger.info("otel_tracing_enabled")
    return True
