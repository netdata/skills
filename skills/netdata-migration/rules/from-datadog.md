# Migrating from Datadog

## What stays, what goes

Remove:

- `dd-trace-*` SDKs and the Datadog Agent.
- `datadog.yaml` on hosts.
- DD-specific env vars: `DD_AGENT_HOST`, `DD_SERVICE`, `DD_ENV`,
  `DD_VERSION`, `DD_TRACE_*`, `DD_LOGS_*`.

Keep (temporarily) during parallel run:

- Datadog Agent. Run it side by side with an OTel Collector until
  cutover validation completes.

Add:

- OpenTelemetry SDK for the service's language (see the
  instrumentation skill).
- An OTel Collector (optional) or direct SDK-to-Netdata OTLP.

## Resource attribute mapping

| Datadog | OpenTelemetry |
|---|---|
| `DD_SERVICE` | `service.name` |
| `DD_VERSION` | `service.version` |
| `DD_ENV` | `deployment.environment` |
| `DD_TAGS=foo:bar,baz:qux` | `OTEL_RESOURCE_ATTRIBUTES=foo=bar,baz=qux` |

## Metric name mapping

Datadog custom metric names survive as-is through the OTel
exporter; set them explicitly where the old code used
`statsd.increment("checkout.orders.count")`:

```python
# Old (dogstatsd)
import datadog
datadog.statsd.increment("checkout.orders.count", tags=["status:success"])

# New (OpenTelemetry)
from opentelemetry import metrics
meter = metrics.get_meter("checkout")
counter = meter.create_counter("checkout.orders.count")
counter.add(1, {"status": "success"})
```

Library-emitted metric names differ. Datadog SDKs produce names
like `trace.http.request.hits`; OTel produces
`http.server.request.count`. Dashboards rebuilt on the Netdata
side use the OTel names.

## Tag vs attribute

Datadog tags are string-only. OpenTelemetry attributes have typed
values but are usually stringified on the wire anyway. Treat them
the same: each tag becomes one attribute key=value.

High-cardinality tags (user id, request id) should not become
metric attributes in either system. Move them to logs.

## Live migration pattern

1. Leave dd-trace running.
2. Add OTel SDK to the same service. Point its exporter at an
   OTel Collector.
3. Configure the Collector with two exporters: the Datadog
   exporter (keeps ddtrace's backend happy for the parallel
   window) and the Netdata exporter.
4. Gradually remove dd-trace from services. Each removal is one
   PR; revert is easy.
5. Once all services are on OTel, drop the Datadog exporter from
   the Collector.

## What Netdata will NOT replicate

- Datadog Notebooks.
- Watchdog anomaly detection (Netdata has its own anomaly
  detection; check the `find_anomalous_metrics` MCP tool).
- SLO dashboards. Netdata has SLO-adjacent features but not
  feature-for-feature parity.
- APM trace exploration. Netdata does not take traces yet.

Route traces to a trace backend (Jaeger, Tempo, external vendor)
until Netdata trace support ships.
