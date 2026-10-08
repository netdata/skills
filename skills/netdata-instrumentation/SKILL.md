---
name: netdata-instrumentation
description: Use when adding OpenTelemetry instrumentation to application code that will report to Netdata. Covers SDK setup, resource attributes, auto-instrumentation, and patterns for Node.js, Python, Java, Go, .NET, Ruby, and PHP. Emits metrics, logs, and traces via OTLP gRPC or HTTP to Netdata. Traces need a Netdata Agent built after 2026-08-17 (nightly) or the first stable release after v2.11.1; stable v2.11.x does not accept them.
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - opentelemetry
  - otel
  - instrumentation
  - sdk
  - nodejs
  - python
  - java
  - golang
  - dotnet
  - ruby
  - php
  - traces
---

# Netdata instrumentation

This skill adds OpenTelemetry instrumentation to application code that
will export metrics, traces, and (where the SDK is mature enough) logs
to Netdata over OTLP/gRPC or OTLP/HTTP.

## When to use this skill

- The user is adding observability to a service for the first time.
- The user wants to replace a vendor SDK (Datadog, New Relic, Dynatrace)
  with OpenTelemetry.
- The user is wiring auto-instrumentation into an existing service.
- The user wants to know what resource attributes Netdata's dashboard
  and MCP tools rely on.
- The user is choosing between SDK-level and Collector-level exporting.

## Key facts

- Export protocol: OTLP/gRPC on port 4317 (on by default), or OTLP/HTTP
  on port 4318 once the Agent sets
  `receivers.otlp.protocols.http.enabled: true`. Both listen on
  `127.0.0.1` by default. SDKs that default to `http/protobuf` can send
  directly once that listener is on, or switch to gRPC.
- Signals: metrics, logs, and traces are accepted on either listener.
  Traces need a Netdata Agent built from `master` after 2026-08-17
  (nightly) or the first stable release after v2.11.1. Stable v2.11.x
  has no trace receiver. Check the target Agent first (see
  `skills/netdata-otel-setup/rules/trace-ingestion.md`):
  - Agent accepts traces: `OTEL_TRACES_EXPORTER=otlp`, pointed at
    Netdata like the other signals.
  - Agent does not accept traces: `OTEL_TRACES_EXPORTER=none`, or a
    separate trace exporter to the current trace backend.
- Spans are explored in the Netdata Traces tab, grouped by
  `service.name`. Viewing requires a signed-in Netdata Cloud user of
  the Agent's Space.
- Resource attributes that matter:
  - `service.name` (required by OTel). Netdata groups charts by this.
  - `service.version`. Used in dashboards and alert rules.
  - `deployment.environment` (or `deployment.environment.name` in the
    newer semconv). Lets the MCP tools filter by env.
  - `host.name`. Filled by most SDKs automatically.
- Prefer auto-instrumentation where it exists (Node.js, Python, Java,
  .NET, Ruby). Hand-code only for Go and PHP, where auto-instrumentation
  is immature or not yet stable.
- Metrics default to delta temporality in many SDKs; Netdata accepts
  both delta and cumulative. Pick cumulative for gauges and sums when
  the backend will be swapped later.
- Environment variables control the exporter without code changes:
  - `OTEL_SERVICE_NAME`
  - `OTEL_EXPORTER_OTLP_ENDPOINT` (scheme + host + port, e.g.
    `http://netdata.example.internal:4317` for gRPC or
    `http://netdata.example.internal:4318` for HTTP)
  - `OTEL_RESOURCE_ATTRIBUTES` (comma-separated key=value list)
  - `OTEL_EXPORTER_OTLP_PROTOCOL`: `grpc` for port 4317, `http/protobuf`
    for port 4318 (be explicit; SDK defaults differ)
  - `OTEL_METRICS_EXPORTER`, `OTEL_TRACES_EXPORTER`,
    `OTEL_LOGS_EXPORTER` (`otlp` or `none` per signal)

## Step-by-step

1. Pick the language rule that matches the service. See [References](#references).
2. Install the OTel packages with the versions listed in that rule.
3. Copy the minimal SDK init into the service's startup path. In
   Node.js/Python this is typically a `-r`/`--import` preload; in Java
   it is the Java agent jar; in Go/Ruby/.NET/PHP it is an in-process
   call before the first work happens.
4. Set the environment variables above. The endpoint uses `http://` (or
   `https://` with TLS) and the port of the chosen protocol. Leave the
   path off `OTEL_EXPORTER_OTLP_ENDPOINT`: HTTP exporters append
   `/v1/metrics`, `/v1/logs`, or `/v1/traces` themselves, and the gRPC
   exporter takes no path. A per-signal variable such as
   `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` is used as-is, so for HTTP it
   carries the full path (OpenTelemetry specification,
   `specification/protocol/exporter.md`).
5. Deploy. Generate some traffic. Verify metrics arrived (see
   [Verification](#verification)). If traces are enabled, open the
   Traces tab and look for the service name.
6. If metrics render in Netdata with unhelpful dimension names, add a
   mapping file. See `skills/netdata-otel-setup/rules/metric-mapping.md`.

## Common mistakes

- Using an HTTP exporter (`http/protobuf`, port 4318) against an Agent
  whose OTLP/HTTP listener is off (the default). Turn the listener on,
  or use gRPC on port 4317. Sending one protocol to the other's port
  fails.
- Forgetting to set `service.name`. Without it, charts group under an
  "unknown_service" bucket and look broken.
- Setting both the SDK endpoint and the Collector endpoint to the same
  Netdata URL. Pick one export path: SDK to Netdata, or SDK to
  Collector to Netdata. Double export doubles the sample count.
- Calling `shutdown()` in the wrong place. Async SDKs need a chance to
  flush on SIGTERM; a blind `process.exit(0)` loses the last batch.
- Enabling trace exporting against a stable v2.11.x (or older) Agent.
  It has no trace receiver; every span export fails. Check trace
  support first.
- Leaving `OTEL_TRACES_EXPORTER=none` from an older setup after the
  Agent gains trace support. No spans reach the Traces tab.
- Sending spans that started more than 24 hours ago or end more than 10
  minutes in the future (clock skew, replayed data). Netdata rejects
  them and reports it through OTLP `partial_success`.
- Hardcoding the endpoint in source. Use the env var. Let ops move the
  endpoint without a code change.

## Choosing SDK export vs Collector export

Two deployment shapes:

- **SDK -> Netdata directly**: simplest. The SDK's OTLP exporter
  (gRPC, or HTTP with the listener on) sends to Netdata. Fine for
  single-service setups or dev environments. The downside is that
  every service carries its own export config and retry logic.
- **SDK -> Collector -> Netdata**: a local (DaemonSet or sidecar)
  Collector intercepts the SDK's OTLP output, adds enrichment
  (Kubernetes metadata, cluster name, etc.), and forwards to
  Netdata. The SDK points at `http://localhost:4317` or
  `http://$HOST_IP:4317`; the Collector handles the real
  destination, TLS, and retries.

Production-shape defaults:

- Single-service or dev: SDK -> Netdata directly.
- Kubernetes, multi-team: SDK -> DaemonSet Collector -> Netdata
  Parent.
- Long-lived serverless / Lambda: SDK -> Netdata directly; the
  Collector lifecycle does not fit a request-scoped runtime.

## Verification

Run an MCP query against the Netdata instance that is supposed to be
receiving the traffic. See the MCP integration skill for the full
transport setup; here is the minimum check:

```bash
# From a shell where the agent with MCP access is configured:
# list_metrics filtered by service name
```

Or via the HTTP API for a quick check without an MCP client:

```bash
curl -s 'http://NETDATA_HOST:19999/api/v2/contexts' \
  | jq --arg svc "$OTEL_SERVICE_NAME" \
       '.contexts | to_entries[] | select(.key | contains($svc))'
```

A non-empty result means at least one metric from the service arrived
within the last few minutes. For traces, open the Traces tab on that
Agent and filter by the service name. For the canonical working
instrumentation (metrics and logs),
see [`tests/e2e/sample-apps/`](../../tests/e2e/sample-apps/) in this repo.

## References

- [`rules/nodejs.md`](./rules/nodejs.md)
- [`rules/python.md`](./rules/python.md)
- [`rules/java.md`](./rules/java.md)
- [`rules/go.md`](./rules/go.md)
- [`rules/dotnet.md`](./rules/dotnet.md)
- [`rules/ruby.md`](./rules/ruby.md)
- [`rules/php.md`](./rules/php.md)
- OpenTelemetry semconv: https://opentelemetry.io/docs/specs/semconv/
- Netdata OTel integration: https://learn.netdata.cloud/docs/collecting-metrics/opentelemetry/opentelemetry-metrics
