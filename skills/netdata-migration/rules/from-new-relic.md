# Migrating from New Relic

## What stays, what goes

Remove:

- `newrelic-*` language agents (`newrelic.jar`, `newrelic.ini`,
  `newrelic.js`, `NewRelic.Agent` NuGet package).
- `newrelic.yml`, `newrelic.config`.
- NR env vars: `NEW_RELIC_LICENSE_KEY`, `NEW_RELIC_APP_NAME`,
  `NEW_RELIC_*`.

Keep (temporarily):

- New Relic Infrastructure or APM agents, until parallel
  validation is done.

Add:

- OpenTelemetry SDK for the service's language.
- OTel Collector (optional).

## Resource attribute mapping

| New Relic | OpenTelemetry |
|---|---|
| `NEW_RELIC_APP_NAME` | `service.name` |
| `NEW_RELIC_APP_INSTANCE` | `service.instance.id` |
| Tag `environment=prod` | `deployment.environment=prod` |
| `NEW_RELIC_LABELS=Region:us-east-1;...` | `OTEL_RESOURCE_ATTRIBUTES=region=us-east-1,...` |

## New Relic's OTLP endpoint (for parallel run)

If you keep shipping to New Relic during cutover, New Relic accepts
OTLP natively at `https://otlp.nr-data.net:4317`. This lets you:

1. Switch the app to OTel SDK immediately.
2. Keep sending OTLP to NR with their license key as a bearer
   token.
3. Add a second OTLP exporter in the Collector pointing at
   Netdata.
4. Decommission the NR branch once parity is confirmed.

```yaml
exporters:
  otlp/newrelic:
    endpoint: otlp.nr-data.net:4317
    headers:
      api-key: YOUR_NR_LICENSE_KEY
  otlp/netdata:
    endpoint: netdata-parent.observability.svc:4317
    tls: { insecure: true }

service:
  pipelines:
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [otlp/newrelic, otlp/netdata]
```

## Custom metrics

New Relic's `newrelic.Metrics.record(...)` calls replace with the
OTel Meter API. Names do not carry over automatically; pick OTel
semantic-convention names where they exist
(`http.server.duration`, `db.client.connections.usage`, ...).

## Transaction traces

New Relic APM's trace view has no direct Netdata equivalent today.
Ship traces to a trace backend (Tempo or NR itself) in parallel.
Netdata trace support lands in a later release.

## What Netdata will NOT replicate

- Workloads, entity relationships, and the "Entity Explorer"
  view. Netdata has a node-centric view instead.
- NR Synthetics (browser/script probes). Use a separate tool
  (Pingdom, Checkly, a cron job with a curl probe).
- Distributed tracing UX. Pending Netdata trace support.
