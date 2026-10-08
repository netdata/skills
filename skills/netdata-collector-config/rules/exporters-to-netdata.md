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


## Signals

One `otlp/netdata` exporter serves every pipeline that lists it:
`metrics`, `logs`, and `traces`. Netdata receives all three on the same
gRPC port. Add the exporter to a `traces` pipeline only when the target
Agent accepts traces (nightly after 2026-08-17, or the first stable
release after v2.11.1). A stable v2.11.x Agent rejects every trace
export; the Collector logs the failure and drops the spans.

## OTLP/HTTP

The Agent's OTLP/HTTP listener (port 4318) is off by default. Once the
Agent sets `receivers.otlp.protocols.http.enabled: true`, the `otlphttp`
exporter works too:

```yaml
exporters:
  otlphttp/netdata:
    endpoint: http://netdata.example.internal:4318
    tls:
      insecure: true
```

Unlike `otlp`, `otlphttp` takes a full URL with a scheme and appends
`/v1/metrics`, `/v1/logs`, or `/v1/traces` itself. Use `https://` and a
`tls` block when the listener has TLS. Source:
`docs/opentelemetry/otlp-ingestion.md` in the Netdata repo.

## TLS-enabled

```yaml
exporters:
  otlp/netdata:
    endpoint: netdata.example.internal:4317
    tls:
      ca_file: /etc/otelcol/netdata-ca.pem
```

For mTLS (Netdata's `tls.client_ca_file` set on the listener), add the
client cert:

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

## Durable sending queue (`file_storage` extension)

The default `sending_queue` lives in memory. A Collector restart loses
whatever the queue held. For pipelines where in-flight data must
survive restarts (typically log ingestion from devices that do not
retransmit), back the queue with the `file_storage` extension. This is
the pattern the
[`syslog-ingest`](https://github.com/netdata/otelcol-cookbook/tree/master/syslog-ingest)
cookbook recipe uses in its durable variant.

```yaml
extensions:
  file_storage/otlp_sending_queue:
    directory: /var/lib/otelcol/filestorage/otlp_sending_queue
    create_directory: true

exporters:
  otlp/netdata:
    endpoint: netdata.example.internal:4317
    tls:
      insecure: true
    sending_queue:
      storage: file_storage/otlp_sending_queue

service:
  extensions:
    - file_storage/otlp_sending_queue
  pipelines:
    logs:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [otlp/netdata]
```

Key points:

- The extension must be listed under `service.extensions` for the
  Collector to load it. The exporter reference alone is not enough.
- The `directory` path must be writable by the user the Collector runs
  as. The cookbook uses `/tmp/...` for demos; production deployments
  should pick a persistent location such as `/var/lib/otelcol/...`.
- One `file_storage` extension can back several exporters by name.
  Each exporter gets its own subdirectory automatically.
- Disk-backed queues protect against Collector restarts and short
  Netdata outages. They do not protect against disk loss; pair with
  the appropriate filesystem durability for the host.

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

- Adding `compression: zstd`. Netdata's OTLP receiver accepts gzip
  and identity only, on both listeners.
- Setting `timeout: 1s`. Too aggressive; Netdata occasionally
  takes longer to ack large batches during ingestion spikes.
  Default of 10s is fine.
- Setting `endpoint: http://netdata:4317` on the `otlp` exporter. The
  scheme breaks the Go gRPC dial. Strip it. (`otlphttp` needs the
  scheme.)
- Pointing the exporter at Netdata's dashboard port only (19999).
  Netdata uses 19999 for web/API/MCP, 4317 for OTLP/gRPC, and 4318
  for OTLP/HTTP. They are different ports by default.
