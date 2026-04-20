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
  --traces_exporter none \
  --logs_exporter none \
  python app.py
```

`--traces_exporter none` and `--logs_exporter none` are important:
Netdata does not yet accept traces, and the Python logs SDK is still
experimental.

## Required environment variables

```bash
export OTEL_SERVICE_NAME=checkout
export OTEL_SERVICE_VERSION=1.4.0
export DEPLOYMENT_ENV=production
export OTEL_EXPORTER_OTLP_ENDPOINT=http://netdata.example.internal:4317
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_METRICS_EXPORTER=otlp
export OTEL_TRACES_EXPORTER=none
export OTEL_LOGS_EXPORTER=none
```

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
