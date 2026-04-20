# Exporter to Netdata

## Base config

```yaml
exporters:
  otlp/netdata:
    endpoint: netdata.example.internal:4317
    tls:
      insecure: true
    sending_queue:
      enabled: true
      num_consumers: 4
      queue_size: 5000
    retry_on_failure:
      enabled: true
      initial_interval: 5s
      max_interval: 30s
      max_elapsed_time: 300s
```

Key points:

- `endpoint` takes `host:port` (no scheme). Most Collector OTLP
  exporters trim schemes but Go is strict.
- `tls.insecure: true` disables TLS. In a same-node DaemonSet
  talking to `127.0.0.1:4317` this is fine. In any cross-host
  exporter, enable TLS.
- `sending_queue` and `retry_on_failure` cope with Netdata
  restarts. The defaults are too conservative; the numbers above
  handle a 5-minute Netdata outage without losing data.

## TLS-enabled

```yaml
exporters:
  otlp/netdata:
    endpoint: netdata.example.internal:4317
    tls:
      ca_file: /etc/otelcol/netdata-ca.pem
```

For mTLS (Netdata's `tls_ca_cert_path` set), add the client cert:

```yaml
tls:
  ca_file: /etc/otelcol/netdata-ca.pem
  cert_file: /etc/otelcol/client-cert.pem
  key_file: /etc/otelcol/client-key.pem
```

See the otel-setup skill's `tls-and-auth.md` for the matching
server-side config.

## Compression

```yaml
exporters:
  otlp/netdata:
    endpoint: netdata.example.internal:4317
    tls:
      insecure: true
    compression: gzip
```

Worth enabling when Collector and Netdata are across a WAN. Pure
LAN/local sockets do not benefit enough to be worth the CPU.

## Multiple Netdatas (Parent + standby Parent)

Two exporter instances, same pipeline:

```yaml
exporters:
  otlp/netdata-primary:
    endpoint: netdata-primary.example.internal:4317
    tls: {insecure: true}
  otlp/netdata-standby:
    endpoint: netdata-standby.example.internal:4317
    tls: {insecure: true}

service:
  pipelines:
    metrics:
      exporters: [otlp/netdata-primary, otlp/netdata-standby]
```

Both Netdatas receive every sample. Use this sparingly; it
doubles upstream load.

## What `sending_queue` sizes to pick

A single Collector with the defaults above (5000 queue size,
4 consumers) buffers roughly 5 minutes of 1000 metrics/sec. Size
by your throughput and tolerated outage window:

```text
queue_size >= metrics_per_second * tolerated_outage_seconds
              / send_batch_size
```

For most node-level DaemonSets with a DaemonSet-to-local-Netdata
setup, defaults are enough.

## Common misconfigurations

- Adding `compression: zstd`. Netdata's gRPC server does gzip and
  identity only.
- Setting `timeout: 1s`. Too aggressive; Netdata occasionally
  takes longer to ack large batches during ingestion spikes.
  Default of 10s is fine.
- Setting `endpoint: http://netdata:4317`. The scheme breaks the
  Go gRPC dial. Strip it.
- Pointing the exporter at Netdata's dashboard port only (19999).
  Netdata uses 19999 for web/API/MCP and 4317 for OTLP. They are
  different ports by default.
