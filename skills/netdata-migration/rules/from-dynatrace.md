# Migrating from Dynatrace

## What stays, what goes

Remove:

- OneAgent per host.
- Application-side SDK calls that use the Dynatrace API.
- `DT_*` environment variables.

Keep (temporarily):

- OneAgent for the parallel-run window.

Add:

- OpenTelemetry SDK for each service's language.
- OTel Collector or direct SDK-to-Netdata OTLP.

## Dynatrace's OTLP endpoint (for parallel run)

Dynatrace accepts OTLP at
`https://{env-id}.live.dynatrace.com/api/v2/otlp` over HTTP (not
gRPC). Netdata accepts OTLP over gRPC, or over HTTP once its OTLP/HTTP
listener is on. During parallel run a Collector fans the same data out
to both backends:

```yaml
exporters:
  otlphttp/dynatrace:
    endpoint: https://ENV_ID.live.dynatrace.com/api/v2/otlp
    headers:
      Authorization: "Api-Token YOUR_DT_TOKEN"
  otlp/netdata:
    endpoint: netdata-parent.observability.svc:4317
    tls: { insecure: true }

service:
  pipelines:
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [otlphttp/dynatrace, otlp/netdata]
    # Only when the Netdata Agent accepts traces
    # (nightly after 2026-08-17, or the first stable release after v2.11.1).
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [otlphttp/dynatrace, otlp/netdata]
```

## Attribute mapping

| Dynatrace | OpenTelemetry |
|---|---|
| `dt.entity.process_group.name` | `service.name` (approximate) |
| `host.name` | `host.name` (same key) |
| `dt.entity.host.group` | custom: `deployment.environment` or `cluster.name` |

Dynatrace's "smart" entity model does not have a direct OTel
counterpart. You will lose the auto-discovered topology; Netdata
builds its own topology from node-level signals.

## OneAgent-specific signals

OneAgent collects signals that the OTel ecosystem equivalents
cover with separate tools:

| OneAgent signal | OTel / Netdata equivalent |
|---|---|
| Host metrics (CPU, memory, disk) | `hostmetrics` receiver, or Netdata native collectors on each host. |
| Process list with auto-discovery | Netdata's `apps.plugin` (native, always on). |
| Log ingestion | `filelog` receiver on the Collector, or OTel SDK logs. |
| Trace auto-instrumentation | OTel Operator `Instrumentation` CRD for zero-code inject, or language-specific SDKs. |

Spans from either path land in Netdata's Traces tab when the Agent
accepts traces.

Note: if you are removing OneAgent from a host and adding a
Netdata Agent, many of these signals are collected by Netdata
natively without OTel. Check the Netdata agent's collectors
directory (`/etc/netdata/`) after install.

## Problem handling

Dynatrace's "Problems" are grouped events. Netdata's alerts are
per-metric thresholds. There is no automatic grouping; rebuild the
alerts manually against Netdata's alert engine.

## What Netdata will NOT replicate

- Davis AI causality analysis.
- Session Replay and RUM (Real User Monitoring). Netdata focuses
  on infrastructure and application telemetry, not browser
  sessions.
- Automated dependency topology. Build an explicit topology (via
  Kubernetes labels, `service.name` conventions, or the
  `k8sattributes` processor).
