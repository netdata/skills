# Collector receivers

## OTLP (the one you always have)

Accept OTLP from producers (SDKs or other Collectors).

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318
```

Enabling both gives clients a choice. The `http` protocol accepts
HTTP/JSON from browsers and legacy tools. Netdata's own receiver is
gRPC-only but the Collector in front of it can be polyglot.

## hostmetrics (node-level signals)

Scrape CPU, memory, disk, network, filesystem, paging from the
host the Collector runs on. Use the DaemonSet pattern so each node
has its own scraper.

```yaml
receivers:
  hostmetrics:
    collection_interval: 10s
    scrapers:
      cpu:
      memory:
      disk:
      filesystem:
      network:
      paging:
      load:
```

Each scraper emits OTLP metrics with instrumentation-scope names
like `otelcol/hostmetricsreceiver/cpuscraper`. Netdata's stock
mapping file handles them. Set `collection_interval` to match
Netdata's expected collection cadence (10s matches Netdata defaults).

## filelog (tail text logs)

For apps that log to files rather than stdout:

```yaml
receivers:
  filelog:
    include:
      - /var/log/nginx/access.log
      - /var/log/myapp/*.log
    operators:
      - type: json_parser
        parse_from: body
        output: timestamp_parser
      - type: timestamp_parser
        parse_from: attributes.ts
        layout: '%Y-%m-%dT%H:%M:%S.%L%z'
```

Use this when you cannot change the application to emit structured
logs via an OTLP SDK. The `operators` list lets you parse, filter,
and enrich each line before exporting.

## kubeletstats (Kubernetes node)

On a DaemonSet, scrape kubelet for per-pod resource usage:

```yaml
receivers:
  kubeletstats:
    collection_interval: 20s
    auth_type: serviceAccount
    endpoint: https://${K8S_NODE_NAME}:10250
    insecure_skip_verify: true
    node: ${K8S_NODE_NAME}
    metric_groups:
      - node
      - pod
      - container
      - volume
```

Pair with the `k8sattributes` processor (see processors.md) so pod
metrics get enriched with namespace, workload, and owner info.

## k8s_cluster (one per cluster)

Run as a Deployment with one replica (not a DaemonSet):

```yaml
receivers:
  k8s_cluster:
    auth_type: serviceAccount
    collection_interval: 30s
    node_conditions_to_report:
      - Ready
      - MemoryPressure
      - DiskPressure
    allocatable_types_to_report:
      - cpu
      - memory
      - storage
```

Emits cluster-wide metrics: node conditions, pod phases, HPA
state, etc. Do not run this as a DaemonSet; the cluster API server
will be hammered N times over.

## syslog (network devices and RFC 3164 / RFC 5424 sources)

Listen for syslog over UDP or TCP and convert each datagram to an OTLP
log record. The canonical end-to-end form lives in the
[`syslog-ingest`](https://github.com/netdata/otelcol-cookbook/tree/master/syslog-ingest)
cookbook recipe; the snippet below is the minimal receiver block.

```yaml
receivers:
  syslog:
    location: "Europe/Athens"  # TODO: timezone for RFC 3164 timestamps
    udp:
      listen_address: "0.0.0.0:53514"
      add_attributes: true
    protocol: rfc3164  # or rfc5424
```

Key points:

- The receiver does not auto-detect the protocol variant. Set
  `protocol: rfc3164` for BSD syslog (the common default) or
  `rfc5424` for the structured RFC 5424 form.
- RFC 3164 timestamps have no timezone or year. `location` is the IANA
  zone used to interpret them. Set this explicitly; the default is
  UTC, which is rarely what the sending device meant.
- Port 514 (UDP) and 601 (TCP) are the IANA-assigned syslog ports but
  both require root. The cookbook uses 53514 because non-root
  Collectors cannot bind below 1024 without `CAP_NET_BIND_SERVICE`.
- `add_attributes: true` attaches the underlying network 5-tuple
  (`net.peer.ip`, `net.host.port`, `net.transport`, etc.) to each log
  record. Pair with the OTTL transform pattern in
  [`processors.md`](./processors.md) to rename these to current OTel
  semantic conventions (`client.address`, `server.port`,
  `network.transport`).
- Use `tcp:` instead of `udp:` for TLS or guaranteed delivery. Most
  network devices only emit UDP.

## prometheus (scrape Prometheus endpoints)

Most Kubernetes infrastructure (kube-state-metrics, node-exporter,
etcd, etc.) already speaks Prometheus. Scrape and convert to OTLP:

```yaml
receivers:
  prometheus:
    config:
      scrape_configs:
        - job_name: kube-state-metrics
          scrape_interval: 30s
          static_configs:
            - targets: ['kube-state-metrics.kube-system:8080']
```

Supports `kubernetes_sd_configs`, `relabel_configs`, etc., exactly
like upstream Prometheus config. The receiver converts scraped
samples to OTLP metrics before they hit the pipeline.

## Picking receivers per pattern

| Pattern | Typical receivers |
|---|---|
| DaemonSet | `otlp`, `hostmetrics`, `filelog`, `kubeletstats` |
| Gateway | `otlp` only (producers push to it) |
| Cluster Deployment | `k8s_cluster`, optionally `prometheus` |
| Edge ingestor | `syslog`, `tcp_log`, `udp_log` (network devices) |
