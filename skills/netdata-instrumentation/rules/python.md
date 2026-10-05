# Python instrumentation

## Install

```bash
pip install \
  opentelemetry-api \
  opentelemetry-sdk \
  opentelemetry-exporter-otlp-proto-grpc \
  opentelemetry-distro \
  opentelemetry-instrumentation-flask \
  opentelemetry-instrumentation-requests
```

The `opentelemetry-distro` package provides the zero-code bootstrap.
Pick per-framework instrumentation packages based on what the service
actually uses. A full list lives at
https://opentelemetry-python-contrib.readthedocs.io/.

## Minimal SDK init

Save as `instrument.py`. Import it before the app imports anything else.

```python
# instrument.py
import logging
import os

from opentelemetry import metrics
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
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

logger_provider = LoggerProvider(resource=resource)
logger_provider.add_log_record_processor(
    BatchLogRecordProcessor(OTLPLogExporter(endpoint=ENDPOINT, insecure=True))
)
set_logger_provider(logger_provider)

handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.INFO)
```

Wire it in at process start:

```python
# app.py
import instrument  # noqa: F401  -- must be first

from flask import Flask

app = Flask(__name__)

@app.route("/hello")
def hello():
    return {"ok": True}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
```

## Auto-instrumentation via opentelemetry-instrument

Instead of the manual init above, run the service under
`opentelemetry-instrument`. It sets up tracing, metrics, and logs SDKs
from environment variables and patches supported libraries.

```bash
opentelemetry-instrument \
  --metrics_exporter otlp \
  --traces_exporter otlp \
  --logs_exporter otlp \
  python app.py
```

`--traces_exporter otlp` sends spans to Netdata. Use
`--traces_exporter none` when the Agent has no trace receiver (stable
v2.11.x or older). `--logs_exporter otlp` wires the Python stdlib `logging`
module to the OTLP logs pipeline, including a `LoggingHandler`
attached to the root logger. No code change to the service is needed
on this path.

## Required environment variables

```bash
export OTEL_SERVICE_NAME=checkout
export OTEL_SERVICE_VERSION=1.4.0
export DEPLOYMENT_ENV=production
export OTEL_EXPORTER_OTLP_ENDPOINT=http://netdata.example.internal:4317
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_METRICS_EXPORTER=otlp
export OTEL_TRACES_EXPORTER=otlp   # "none" if the Agent has no trace receiver
export OTEL_LOGS_EXPORTER=otlp
```

## Traces with the manual init

The manual `instrument.py` above sets up metrics and logs only. To send
spans, add a tracer provider with the gRPC span exporter (shipped in
`opentelemetry-exporter-otlp-proto-grpc`):

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint=ENDPOINT, insecure=True))
)
trace.set_tracer_provider(tracer_provider)
```

Add it only when the Agent accepts traces (nightly after 2026-08-17, or
the first stable release after v2.11.1). Spans appear in the Traces tab
under the service name.

## What Netdata does with OTLP logs

OTLP/gRPC log ingestion is always on once `otel-plugin` is running.
On v2.11.0 and later, records are indexed under
`/var/log/netdata/otel/v2/logs` and explored in the Logs tab
(`otel-logs` source, filtered by service). Retention lives under
`logs.retention` in `otel.yaml`; stock defaults keep up to 1 GB or 7
days, whichever comes first. Full reference:
[`netdata-otel-setup/rules/log-ingestion.md`](../../netdata-otel-setup/rules/log-ingestion.md).

## Framework notes

- **Flask**: `opentelemetry-instrumentation-flask` wraps `app.run`. With
  `opentelemetry-instrument`, nothing else is needed.
- **FastAPI**: use `opentelemetry-instrumentation-fastapi`. Call
  `FastAPIInstrumentor.instrument_app(app)` after the app object is
  created.
- **Django**: use `opentelemetry-instrumentation-django`. Set the env
  var `DJANGO_SETTINGS_MODULE` before `opentelemetry-instrument` runs.
- **gunicorn / uwsgi**: the preload path is tricky. Put the init in a
  module that the worker imports after fork, not in the master. See
  the `gunicorn --preload` pitfalls in the OTel Python docs.

## Verification

```bash
curl -s 'http://NETDATA_HOST:19999/api/v2/contexts' \
  | jq --arg svc "$OTEL_SERVICE_NAME" \
       '.contexts | to_entries[] | select(.key | contains($svc))'
```

A non-empty result means at least one metric from the service arrived.

## Worked example

The runnable version of this pattern lives at
[`tests/e2e/sample-apps/python/`](../../../tests/e2e/sample-apps/python/).
The fixture imports `instrument.py` from the service entry point and
uses the exact init code shown above.
