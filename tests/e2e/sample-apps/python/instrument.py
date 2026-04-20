# instrument.py
import os

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

resource = Resource.create(
    {
        "service.name": os.environ.get("OTEL_SERVICE_NAME", "unnamed-service"),
        "service.version": os.environ.get("OTEL_SERVICE_VERSION", "0.0.0"),
        "deployment.environment": os.environ.get("DEPLOYMENT_ENV", "development"),
    }
)

reader = PeriodicExportingMetricReader(
    exporter=OTLPMetricExporter(endpoint=ENDPOINT, insecure=True),
    export_interval_millis=5000,
)

metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))
