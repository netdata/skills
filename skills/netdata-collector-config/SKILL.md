---
name: netdata-collector-config
description: Use when building or modifying an OpenTelemetry Collector pipeline that forwards telemetry to Netdata. Covers receivers, processors, exporters, and three deployment patterns (DaemonSet, gateway, and OpenTelemetry Operator). Teaches how to shape chart dimensions via an OTLP attribute plus a mapping file, since Netdata does not expose producer-driven annotations for chart layout.
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - opentelemetry
  - otel
  - otel-collector
  - kubernetes
  - daemonset
  - gateway
---

# Netdata Collector config

This skill builds an OpenTelemetry Collector pipeline whose exporter
is a Netdata Agent or Parent. The Collector runs where the raw data
is (node, sidecar, or gateway) and hands a cleaned OTLP stream to
Netdata.

## When to use this skill

- The user wants to deploy the OTel Collector on Kubernetes with
  Netdata as the backend.
- The user is adding a hostmetrics or `filelog` receiver alongside
  their application's OTLP.
- The user wants to aggregate cluster-wide telemetry at a gateway
  before exporting to a Netdata Parent.
- The user is using the OpenTelemetry Operator and wants to know
  what CRD shape to use.

## Key facts

- Netdata receives OTLP over gRPC (port 4317, on by default) or
  HTTP (port 4318, once the Agent sets
  `receivers.otlp.protocols.http.enabled: true`). The Collector's
  `otlp` exporter speaks gRPC and works with a stock Agent. The
  `otlphttp` exporter takes a full URL (`http://HOST:4318`) and
  needs the Agent's OTLP/HTTP listener.
- TLS on the Collector-to-Netdata hop is configured on the
  exporter's `tls:` block. Netdata's server-side config is covered
  in the otel-setup skill.
- For Kubernetes: three common patterns, each with trade-offs.
  - **DaemonSet**: one Collector per node, scraping node-local
    signals and the pods on that node. Lowest-latency, highest pod
    count. Recommended default.
  - **Gateway (Deployment)**: one Collector pool, every producer
    pushes to it, it batches and forwards to Netdata. Simplifies
    configuration at the cost of an extra hop and extra failure
    mode.
  - **Operator-managed**: `OpenTelemetryCollector` CRD manages the
    DaemonSet or Deployment. Best when you want declarative
    lifecycle.
- Netdata accepts metrics, logs, and traces over the same
  `otlp/netdata` exporter. Traces need a Netdata Agent built from
  `master` after 2026-08-17 (nightly) or the first stable release
  after v2.11.1; stable v2.11.x has no trace receiver. Check the
  target Agent before adding a `traces` pipeline (see the otel-setup
  skill, `rules/trace-ingestion.md`). Against an Agent without trace
  support, keep traces on their current backend.
- Traces are stored and queried on the Agent that receives the OTLP
  export. Point the `traces` pipeline at the Agent (usually a Parent)
  where users will open the Traces tab. Whether received traces
  replicate to a Parent through Netdata streaming is not documented;
  do not assume they do.
- Chart shape on the Netdata side is controlled by **mapping
  files** on the Netdata host, not by annotations the Collector
  adds. To pick the dimension name, set an attribute on the
  data point (via `resource` or `transform` processors) and name
  that attribute as `dimension_attribute_key` in the mapping file.
  See the otel-setup skill.

## Step-by-step

1. Pick the deployment pattern. See the `rules/*-deployment.md`
   files.
2. Build a minimal Collector config with:
   - a single `otlp` receiver (and any node-local receivers like
     `hostmetrics` or `filelog`),
   - a small processor chain (`memory_limiter`, `batch`, optional
     `resource`),
   - a single `otlp` exporter pointing at Netdata, used by the
     `metrics`, `logs`, and (when the Agent supports them) `traces`
     pipelines.
3. Deploy the Collector.
4. Point producers at the Collector's OTLP port (default 4317).
5. Verify data arrives at Netdata using the MCP integration skill.

## Common mistakes

- Pointing the `otlphttp` exporter at port 4317, or at an Agent
  whose OTLP/HTTP listener is off (the default). Use port 4318 with
  the listener on, or the `otlp` exporter on port 4317.
- Adding a `traces` pipeline against a stable v2.11.x Agent. It has
  no trace receiver, so every trace export fails and the Collector
  drops the spans. Check trace support first.
- Sampling traces in the DaemonSet tier. `tail_sampling` needs every
  span of a trace on one Collector; run it on a gateway behind a
  trace-ID-aware load balancer.
- Not setting `memory_limiter` before `batch`. Under pressure the
  Collector OOMs; `memory_limiter` is the circuit breaker.
- Sending `hostmetrics` without a matching mapping file on
  Netdata. The stock `hostmetrics-receiver.yaml` mapping handles
  most of these, but the Collector-side scope name must match the
  mapping regex (`.*hostmetricsreceiver.*cpuscraper$` etc.).
- Running the Collector and the producer SDK both exporting to
  Netdata. Each sample appears twice. Pick one.

## Image and versioning

Use `otel/opentelemetry-collector-contrib` rather than
`otel/opentelemetry-collector`. The contrib distribution includes
the `hostmetrics`, `kubeletstats`, `k8sattributes`, `prometheus`,
and `filelog` components that a Netdata-bound pipeline usually
needs. The core image omits them.

Pin to a minor version tag (for example `0.109.0`) rather than
`latest`. Collector minor versions drop or rename components
occasionally; pinning avoids silent config breakage on a rolling
image update.

## Memory and CPU sizing

Back-of-the-envelope:

- `memory_limiter` should be 60%-75% of the container's memory
  limit. Going higher gives the GC no room.
- `batch.send_batch_size` of 8192 suits most loads. Increase only
  when exporter queue latency is the bottleneck.
- CPU: 0.1 vCPU per 1000 metrics/second is a rough upper bound
  for the common processor set. Enable a Go `pprof` endpoint in
  staging if you need a real number.

## Verification

On the Netdata side, use the MCP integration skill's
`verify-telemetry-flow.md` patterns. A specific Collector-oriented
probe:

```text
list_metrics filtered by attribute otel.scope.name matching
".*hostmetricsreceiver.*". Return distinct scope names.
```

If the hostmetrics scopes do not appear, the Collector is either not
running, not scraping, or not exporting successfully.

A lower-level probe hits the Collector's own telemetry. Enable it
in the Collector config:

```yaml
service:
  telemetry:
    metrics:
      readers:
        - pull:
            exporter:
              prometheus:
                host: "0.0.0.0"
                port: 8888
```

Then:

```bash
curl -s http://COLLECTOR_HOST:8888/metrics \
  | grep 'otelcol_exporter_sent_'
```

A non-zero `otelcol_exporter_sent_metric_points` counter for
`exporter=otlp/netdata` confirms metrics left the Collector. If
that number is rising but Netdata is not seeing them, the
problem is on the Netdata receiver side; run the otel-setup
troubleshooting ladder.

## Recipes

For end-to-end Collector configurations tested against Netdata, consult
the [Netdata OpenTelemetry Collector Cookbook](https://github.com/netdata/otelcol-cookbook).
Each recipe directory in that repo ships a complete `otelcol.yaml` plus
a `README.md` explaining the use case and any required edits.

When the cookbook covers a pattern the user is asking for, fetch the
recipe directly from the source of truth rather than reconstructing it
here. See [`rules/recipes.md`](./rules/recipes.md) for how to look up
the current recipe list at the moment of use and the conventions each
recipe follows.

## References

- [`rules/receivers.md`](./rules/receivers.md)
- [`rules/processors.md`](./rules/processors.md)
- [`rules/exporters-to-netdata.md`](./rules/exporters-to-netdata.md)
- [`rules/daemonset-deployment.md`](./rules/daemonset-deployment.md)
- [`rules/gateway-deployment.md`](./rules/gateway-deployment.md)
- [`rules/otel-operator.md`](./rules/otel-operator.md)
- [`rules/recipes.md`](./rules/recipes.md)
- OTel Collector docs: https://opentelemetry.io/docs/collector/
- OTel Operator: https://github.com/open-telemetry/opentelemetry-operator
- Netdata OTel Collector Cookbook: https://github.com/netdata/otelcol-cookbook
