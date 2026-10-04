# Gateway deployment pattern

## What and why

One Collector pool (Deployment + Service, 2-10 replicas) that
every producer pushes to. The gateway batches, enriches, filters,
then exports to Netdata.

Use a gateway when:

- You want one place to edit filtering/enrichment rules.
- You want to terminate TLS/auth at the edge.
- You have many producers that should not each carry Netdata
  credentials.
- You want to route subsets of telemetry to different backends
  (e.g., metrics and traces to Netdata, a copy of traces to an
  existing trace backend during a migration).
- You want tail-based trace sampling. It needs every span of a
  trace on one Collector, which a gateway (behind a trace-ID-aware
  load balancer) can provide.

Do not use a gateway as the only collection tier when you also
need node-level signals; those need a DaemonSet. It is common to
run both: DaemonSet for node-local sources, Gateway for app
telemetry.

## Shape

```text
[ SDK / DaemonSet ]  -->  [ Gateway Deployment ]  -->  [ Netdata ]
                              (N replicas)          (metrics, logs, traces)
                                       |
                                       +-->  [ Other backend ] (optional)
```

## Config

```yaml
receivers:
  otlp:
    protocols:
      grpc: { endpoint: 0.0.0.0:4317 }
      http: { endpoint: 0.0.0.0:4318 }

processors:
  memory_limiter:
    check_interval: 1s
    limit_percentage: 75
    spike_limit_percentage: 15
  resource:
    attributes:
      - key: cluster.name
        value: prod-us-east-1
        action: upsert
  batch:
    send_batch_size: 16384
    timeout: 10s

exporters:
  otlp/netdata:
    endpoint: netdata-parent.observability.svc:4317
    tls: { insecure: true }
    sending_queue:
      enabled: true
      queue_size: 20000
      num_consumers: 8

service:
  pipelines:
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, resource, batch]
      exporters: [otlp/netdata]
    logs:
      receivers: [otlp]
      processors: [memory_limiter, resource, batch]
      exporters: [otlp/netdata]
    # Only when the target Agent accepts traces (nightly after
    # 2026-08-17, or the first stable release after v2.11.1).
    traces:
      receivers: [otlp]
      processors: [memory_limiter, resource, batch]
      exporters: [otlp/netdata]
```

Batch size and queue size are bigger than on a DaemonSet because
the gateway processes many producers' traffic in one place.

## Deployment + Service

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: otel-gateway
  namespace: otel
spec:
  replicas: 3
  selector: { matchLabels: { app: otel-gateway } }
  template:
    metadata: { labels: { app: otel-gateway } }
    spec:
      containers:
        - name: collector
          image: otel/opentelemetry-collector-contrib:0.109.0
          args: [--config=/conf/otel-collector-config.yaml]
          resources:
            limits: { memory: 2Gi, cpu: 1 }
            requests: { memory: 512Mi, cpu: 200m }
          volumeMounts:
            - { name: config, mountPath: /conf }
      volumes:
        - name: config
          configMap: { name: otel-gateway }
---
apiVersion: v1
kind: Service
metadata:
  name: otel-gateway
  namespace: otel
spec:
  selector: { app: otel-gateway }
  ports:
    - { name: grpc, port: 4317 }
    - { name: http, port: 4318 }
```

Producers point at `otel-gateway.otel.svc.cluster.local:4317`.

## Horizontal Pod Autoscaler

gRPC connections are sticky, so HPA-driven scale-up only helps new
producers. For bursty traffic, prefer sizing replicas for peak
load plus 20% headroom.

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: otel-gateway
  namespace: otel
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: otel-gateway
  minReplicas: 3
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target: { type: Utilization, averageUtilization: 70 }
```

## Mixing gateway and DaemonSet

Run both:

- DaemonSet: `hostmetrics`, `kubeletstats`, `filelog`. Exports to
  Netdata directly (skip the gateway for node-local signals).
- Gateway: receives application OTLP, enriches, forwards to
  Netdata.

This keeps the high-volume node telemetry out of the gateway's
buffer and still gives the application telemetry a single
control point.
