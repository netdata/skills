# Collector processors

## The short chain every pipeline needs

```yaml
processors:
  memory_limiter:
    check_interval: 1s
    limit_percentage: 75
    spike_limit_percentage: 15
  batch:
    send_batch_size: 8192
    timeout: 10s
```

`memory_limiter` first, `batch` right before the exporter. Order
matters: `memory_limiter` drops samples when pressure spikes so
`batch` never holds more than the Collector can export.

## resource (add service identity)

```yaml
processors:
  resource:
    attributes:
      - key: deployment.environment
        value: production
        action: upsert
      - key: cluster.name
        value: prod-us-east-1
        action: upsert
```

Use for defaulting resource attributes the producer might forget.
`upsert` adds the key if missing; `insert` skips if present;
`update` only modifies existing keys.

## attributes (per-datapoint knobs)

Shape the attributes that end up on each OTLP data point. Useful
for adding or renaming the attribute that Netdata's mapping file
will use as `dimension_attribute_key`.

```yaml
processors:
  attributes/dimension_label:
    actions:
      - key: instance
        from_attribute: host.name
        action: insert
      - key: mysql.client_pid
        action: delete  # drop a high-cardinality attribute
```

## k8sattributes (pod enrichment)

Enriches each record with pod/namespace/workload/ownerRef fields
pulled from the Kubernetes API:

```yaml
processors:
  k8sattributes:
    auth_type: serviceAccount
    passthrough: false
    extract:
      metadata:
        - k8s.namespace.name
        - k8s.pod.name
        - k8s.pod.uid
        - k8s.deployment.name
        - k8s.node.name
      labels:
        - tag_name: app
          key: app.kubernetes.io/name
          from: pod
    pod_association:
      - sources:
          - from: resource_attribute
            name: k8s.pod.ip
      - sources:
          - from: connection
```

Requires RBAC to read `pods` and `namespaces`. Pair it with every
pipeline that has a receiver scraping inside the cluster.

## transform (OTTL, surgical rewrites)

OpenTelemetry Transform Language (OTTL) lets you rewrite metric
names, move attributes, or drop records conditionally:

```yaml
processors:
  transform/metric_renames:
    error_mode: ignore
    metric_statements:
      - context: metric
        statements:
          - set(name, "http.server.duration") where name == "http.server.request.duration"
```

Set `error_mode: ignore` on any transform that runs against
heterogeneous input. The default error mode (`propagate`) drops the
whole batch on a single failing statement; `ignore` skips only the
failing record. Use `silent` when you also want to suppress the log
line each failure emits.

Prefer OTTL over custom processors; the config is text-reviewable
and version-stable.

### Promoting log attributes to resource attributes

Receivers such as `syslog`, `udp_log`, and `filelog` place every
parsed field under `log.attributes`. Netdata uses resource attributes
to group records by service or host, so identity fields belong on the
resource. The cookbook's
[`syslog-ingest`](https://github.com/netdata/otelcol-cookbook/tree/master/syslog-ingest)
recipe demonstrates the pattern:

```yaml
processors:
  transform/syslog:
    error_mode: ignore
    log_statements:
      - set(resource.attributes["host.name"], log.attributes["hostname"])
      - delete_key(log.attributes, "hostname")
      - set(resource.attributes["process.pid"], log.attributes["proc_id"])
        where log.attributes["proc_id"] != nil
      - delete_key(log.attributes, "proc_id")
      - set(log.attributes["log.record.original"], log.body)
      - set(log.body, log.attributes["message"])
      - delete_key(log.attributes, "message")
```

The `set` then `delete_key` pair moves a field. Guarding the move with
`where ... != nil` skips records that lack the field rather than
emitting a null attribute. Preserve the unparsed datagram in
`log.record.original` before overwriting `log.body`; downstream tools
that need the raw form still have it.

### Migrating to current OTel semantic conventions

The `net.*` attribute namespace was renamed during the
OpenTelemetry semconv stabilization. Receivers that emit the old
names (`net.peer.ip`, `net.host.port`, `net.transport`) need a
translation step so Netdata sees the current names. The cookbook's
`syslog-ingest` recipe carries the full block; the shape is:

```yaml
- set(log.attributes["client.address"], log.attributes["net.peer.ip"])
  where log.attributes["net.peer.ip"] != nil
- delete_key(log.attributes, "net.peer.ip")
- set(log.attributes["server.port"], Int(log.attributes["net.host.port"]))
  where log.attributes["net.host.port"] != nil
- delete_key(log.attributes, "net.host.port")
```

Cast strings to integers with `Int(...)` so port and PID attributes
land as numeric types rather than as quoted strings.

## filter (drop what you do not need)

```yaml
processors:
  filter/drop_debug:
    metrics:
      include:
        match_type: strict
        metric_names: []
      exclude:
        match_type: regexp
        metric_names:
          - '.*\.debug\..*'
```

Use to strip internal/debug metrics that a careless SDK default
leaves enabled.

## A representative pipeline

```yaml
service:
  pipelines:
    metrics:
      receivers: [otlp, hostmetrics]
      processors: [memory_limiter, k8sattributes, resource, batch]
      exporters: [otlp/netdata]
    logs:
      receivers: [otlp, filelog]
      processors: [memory_limiter, k8sattributes, resource, batch]
      exporters: [otlp/netdata]
```

Notice: `memory_limiter` always first, `batch` always last. No
trace pipeline against Netdata.

## What NOT to put in a Netdata pipeline

- `tailsampling` / `probabilistic_sampler`: these are trace-only.
- `spanmetrics`: generates metrics from traces; fine as long as
  the input traces go to a real trace backend, but do not add
  this to a Netdata-bound pipeline that has no trace source.
