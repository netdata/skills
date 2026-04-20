# OpenTelemetry Operator

## What it is

A Kubernetes operator that manages OpenTelemetry Collector
instances via the `OpenTelemetryCollector` CRD. Use it when you
want declarative Collector lifecycle on Kubernetes.

## Install

```bash
kubectl apply -f https://github.com/open-telemetry/opentelemetry-operator/releases/latest/download/opentelemetry-operator.yaml
```

Cert-manager is a dependency. If the cluster does not run it
already:

```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml
```

## `OpenTelemetryCollector` CRD (DaemonSet mode)

```yaml
apiVersion: opentelemetry.io/v1beta1
kind: OpenTelemetryCollector
metadata:
  name: node-agent
  namespace: otel
spec:
  mode: daemonset
  image: otel/opentelemetry-collector-contrib:0.109.0
  serviceAccount: otel-collector-daemonset
  resources:
    requests: { memory: 128Mi, cpu: 100m }
    limits:   { memory: 512Mi, cpu: 500m }
  config:
    receivers:
      otlp:
        protocols:
          grpc: { endpoint: 0.0.0.0:4317 }
      hostmetrics:
        collection_interval: 10s
        scrapers:
          cpu: {}
          memory: {}
          disk: {}
          filesystem: {}
          network: {}

    processors:
      memory_limiter:
        check_interval: 1s
        limit_percentage: 75
        spike_limit_percentage: 15
      batch:
        send_batch_size: 8192
        timeout: 10s

    exporters:
      otlp/netdata:
        endpoint: netdata-parent.observability.svc:4317
        tls: { insecure: true }

    service:
      pipelines:
        metrics:
          receivers: [otlp, hostmetrics]
          processors: [memory_limiter, batch]
          exporters: [otlp/netdata]
```

The operator materializes a DaemonSet, ConfigMap, and Service
from this CR. Delete the CR, and all three go away.

## Gateway mode

```yaml
apiVersion: opentelemetry.io/v1beta1
kind: OpenTelemetryCollector
metadata:
  name: gateway
  namespace: otel
spec:
  mode: deployment
  replicas: 3
  image: otel/opentelemetry-collector-contrib:0.109.0
  config:
    # same config shape as above, but only receivers: [otlp]
```

## Sidecar mode (per-pod)

```yaml
spec:
  mode: sidecar
```

The operator injects a Collector container into any pod annotated
with `sidecar.opentelemetry.io/inject: "gateway-config"` (or the
CR name). Useful when the pod cannot reach a DaemonSet (for
example, in ServiceMesh setups with strict egress rules).

## Instrumentation CRD (auto-inject SDKs)

The operator can also inject language SDKs into pods via the
`Instrumentation` CRD. This replaces manually editing every
deployment to install OTel SDK libraries.

```yaml
apiVersion: opentelemetry.io/v1alpha1
kind: Instrumentation
metadata:
  name: auto-instrument
  namespace: otel
spec:
  exporter:
    endpoint: http://otel-gateway.otel.svc:4317
  propagators:
    - tracecontext
    - baggage
  sampler:
    type: parentbased_always_on
  env:
    - name: OTEL_METRICS_EXPORTER
      value: otlp
    - name: OTEL_TRACES_EXPORTER
      value: none
    - name: OTEL_LOGS_EXPORTER
      value: none
  nodejs:
    image: ghcr.io/open-telemetry/opentelemetry-operator/autoinstrumentation-nodejs:latest
  python:
    image: ghcr.io/open-telemetry/opentelemetry-operator/autoinstrumentation-python:latest
  java:
    image: ghcr.io/open-telemetry/opentelemetry-operator/autoinstrumentation-java:latest
  dotnet:
    image: ghcr.io/open-telemetry/opentelemetry-operator/autoinstrumentation-dotnet:latest
```

Pods opt in via annotation:

```yaml
metadata:
  annotations:
    instrumentation.opentelemetry.io/inject-nodejs: "auto-instrument"
```

The operator handles the init container that copies the SDK into
the app container's filesystem and the env-var wiring.

Note the `OTEL_TRACES_EXPORTER=none` and
`OTEL_LOGS_EXPORTER=none`: Netdata does not accept traces, and the
auto-instrumentation's logs exporter is often more trouble than
it is worth. Start with metrics only, add more signals once the
baseline works.

## When not to use the operator

- Very small clusters. The operator adds two pods (controller +
  webhook) plus cert-manager. For a 3-node cluster with one
  DaemonSet, this is overhead.
- Non-Kubernetes (Nomad, ECS, bare metal, systemd). The operator
  is Kubernetes-only.
