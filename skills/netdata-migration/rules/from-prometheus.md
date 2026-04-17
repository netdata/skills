# Migrating from Prometheus

## Paths

Three ways to keep Prometheus metrics flowing into Netdata:

1. **Netdata native Prometheus collector**: Netdata scrapes
   Prometheus endpoints directly. Fastest path, zero Collector
   required. Configure via the `go.d` Prometheus collector.
2. **OTel Collector prometheus receiver**: convert scraped
   Prometheus samples into OTLP and forward to Netdata.
3. **Keep Prometheus server, add remote_write to Netdata**:
   Prometheus `remote_write` is not accepted by Netdata's OTLP
   endpoint. Use path 1 or 2 instead.

Path 1 is the usual choice for all-Netdata installs. Path 2 is
the right choice when you already run an OTel Collector.

## Path 1: Netdata's native Prometheus collector

Configure the `go.d.plugin` collector for Prometheus endpoints.
File: `/etc/netdata/go.d/prometheus.conf`.

```yaml
jobs:
  - name: kube-state-metrics
    url: http://kube-state-metrics.kube-system:8080/metrics
    timeout: 5s
    selector:
      allow:
        - 'kube_*'

  - name: node-exporter-prod-01
    url: http://prod-01.example.internal:9100/metrics
```

Restart Netdata:

```bash
sudo systemctl restart netdata
```

Netdata creates charts for every scraped series automatically.
The collector does basic de-duplication and type detection; use
`selector` to filter noise.

## Path 2: OTel Collector prometheus receiver

```yaml
receivers:
  prometheus:
    config:
      scrape_configs:
        - job_name: kube-state-metrics
          scrape_interval: 30s
          static_configs:
            - targets:
                - 'kube-state-metrics.kube-system:8080'
        - job_name: node-exporter
          kubernetes_sd_configs:
            - role: node
          relabel_configs:
            - source_labels: [__address__]
              action: replace
              regex: '(.+?):(.+?)'
              replacement: '${1}:9100'
              target_label: __address__

processors:
  batch:
    send_batch_size: 16384
    timeout: 10s

exporters:
  otlp/netdata:
    endpoint: netdata-parent.observability.svc:4317
    tls: { insecure: true }

service:
  pipelines:
    metrics:
      receivers: [prometheus]
      processors: [batch]
      exporters: [otlp/netdata]
```

The Collector produces OTLP data points with instrumentation
scope `prometheusreceiver`. If you need specific dimension names
on the Netdata side, add a mapping file under
`/etc/netdata/otel.d/v1/metrics/` with a matching scope regex.

## Promethus label vs OTel attribute

Prometheus labels become OTel attributes on the data point.
Cardinality that was fine in Prometheus (e.g., `pod`, `instance`)
is often fine in Netdata too; Netdata's mapping engine treats
attribute values as chart dimensions.

Some labels are redundant in OTel. For example, Prometheus's
`instance` label is often replaced by `service.instance.id`.

## Decommissioning the Prometheus server

You can stop Prometheus if:

- Every alert has been rebuilt against Netdata.
- Every Grafana dashboard has been either migrated or rebuilt
  (Grafana supports Netdata as a data source; see Netdata docs).
- Recording rules have been rebuilt. Netdata does not run
  Prometheus recording rules natively; use mapping files or
  pre-compute in the producer.

If Grafana stays, Netdata exposes a Prometheus-compatible query
endpoint that Grafana can use as a fallback data source.

## Long-term storage

Prometheus with Thanos/Cortex/Mimir provides long-term storage.
Netdata has its own long-term storage layer (tiered dbengine).
Check that Netdata's retention matches or exceeds what the
Prometheus long-term store holds. Default Netdata retention is
configurable in `/etc/netdata/netdata.conf`.
