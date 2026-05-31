# Translating a rule

This is the method for a rule that survived the decision tree in
[`choose-what-to-migrate.md`](./choose-what-to-migrate.md): no stock
equivalent, the metric is collected by Netdata, and the expression is
a single-metric threshold. The target DSL is in
[`netdata-health-alerts.md`](./netdata-health-alerts.md).

## The model mapping

A PromQL alert is `selector -> aggregate -> compare -> for`. A Netdata
alert is `on context -> lookup dimensions over a window -> calc ->
warn/crit`. Map the parts:

1. **Selector to context.** Find the Netdata chart context that holds
   the metric. The Prometheus metric name and its `{label=...}`
   matchers become the `on:` context plus `chart labels:` / `host
   labels:` scoping, and the dimension(s) named in `lookup ... of`.
2. **Per-series fan-out to template.** A Prometheus rule fires one
   alert per label set (per instance, per device). Use `template:` so
   the alert fans across every chart of the context, and `chart
   labels:` to restrict which instances.
3. **Range aggregation to lookup method.** `avg_over_time` becomes
   `lookup: average`, `max_over_time` becomes `lookup: max`, and so
   on. The range `[5m]` becomes the lookup window `-5m`.
4. **Threshold to warn/crit.** The comparison becomes a `warn:` or
   `crit:` expression, wrapped in the hysteresis idiom.
5. **for to window plus delay.** Netdata has no `for:`. Approximate.

## Field-by-field

| Prometheus / vmalert | Netdata health |
| --- | --- |
| `alert: Name` | `template: name` (or `alarm:`) |
| metric name + `{matchers}` | `on: <context>` + `chart labels:`/`host labels:` |
| dimension within the metric | `lookup: ... of <dimension>` |
| `avg_over_time(m[5m])` | `lookup: average -5m unaligned of <dim>` |
| `max_over_time`/`min`/`sum_over_time` | `lookup: max/min/sum -5m` |
| `quantile_over_time(0.95, m[5m])` | `lookup: percentile95 -5m` |
| arithmetic on one chart's dims | `calc:` |
| `> T` / `< T` | `warn:`/`crit: $this > T` with hysteresis |
| `severity: warning` vs `critical` | the `warn:` line vs the `crit:` line |
| `for: 5m` | lookup window near 5m, plus `delay: up 5m` |
| `annotations.summary` | `summary:` |
| `annotations.description` | `info:` |
| `{{ $labels.instance }}` | `${label:<name>}` |
| `{{ $value }}` | shown automatically in the notification |
| group `interval:` | `every:` |
| Alertmanager routing | `to: <role>` (see notifications rule) |

## Mapping the query language

- **Label matchers** (`=`, `=~`) become `chart labels:` / `host
  labels:` patterns. `{mountpoint="/var"}` becomes
  `chart labels: mount_point=/var`. `{device=~"sd.*"}` becomes
  `chart labels: device=sd*`.
- **rate / irate / increase over a counter.** Netdata usually charts
  the per-second rate already (a dimension with the incremental
  algorithm), so a `rate(...)` threshold often becomes a plain
  `lookup` on the rate dimension. If the chart stores a raw counter
  and you want the increase over a window, use
  `lookup: incremental_sum -5m`.
- **`*_over_time`** reducers map directly to lookup methods (table
  above).
- **Scalar arithmetic** on one metric (`m / 1024`, `100 - m`) becomes
  `calc:`. Arithmetic across two different metrics is a hard case; see
  [`hard-cases.md`](./hard-cases.md).
- **`bool`** comparisons (`m > bool 5`) become a `calc:` returning
  the 1/0 directly (Netdata comparisons already yield 1/0).

## Approximating `for:`

Netdata has no exact `for:`. Three honest options, pick per intent:

- **Window averaging (default).** Set the `lookup` window to roughly
  the `for:` duration with `average`. The alert fires when the
  windowed average crosses the threshold, which suppresses brief
  spikes much like `for:` does. `expr > 90 for 10m` becomes
  `lookup: average -10m` plus `warn: $this > 90`.
- **delay on notification.** Add `delay: up <for>` so the notification
  is held until the alert has been raised that long. This delays the
  alert reaching a human, not the state change.
- **Strict continuity.** For "the value was above T for the entire
  window," use `lookup: min -10m` (even the lowest sample in the
  window exceeded T). Use sparingly; it is stricter than `for:`.

State which you used; do not imply exact `for:` parity.

## Worked example 1: a clean single-metric threshold

Source (vmalert / Prometheus):

```yaml
- alert: QueueBacklog
  expr: avg_over_time(myapp_queue_depth[5m]) > 1000
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Queue backlog on {{ $labels.instance }}"
    description: "Queue depth has averaged {{ $value }} over 5m"
```

Assume Netdata collects this as context `myapp.queue` with dimension
`depth`. Translation:

```text
template: myapp_queue_backlog
      on: myapp.queue
  lookup: average -5m unaligned of depth
   units: items
   every: 10s
    warn: $this > (($status >= $WARNING)  ? (800)  : (1000))
    crit: $this > (($status == $CRITICAL) ? (1000) : (1500))
   delay: up 5m
 summary: Queue backlog on ${label:instance}
    info: Average myapp queue depth over the last 5 minutes
      to: sysadmin
```

## Worked example 2: a ratio on one chart (percentage)

Source:

```yaml
- alert: HighMemory
  expr: 100 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes * 100) > 90
  for: 15m
```

Netdata charts memory on `system.ram` with dimensions `used`,
`cached`, `free`, `buffers`. The ratio is arithmetic on one chart, so
use `calc` (no lookup needed for an instantaneous percentage):

```text
   alarm: high_ram_usage
      on: system.ram
    calc: $used * 100 / ($used + $cached + $free + $buffers)
   units: %
   every: 10s
    warn: $this > (($status >= $WARNING)  ? (80) : (90))
    crit: $this > (($status == $CRITICAL) ? (90) : (98))
    info: RAM utilization
      to: sysadmin
```

In practice this signal is stock (`ram_in_use`); the example shows the
mechanics of a cross-dimension ratio that stays on one chart.

## Worked example 3: a counter rate threshold

Source:

```yaml
- alert: HighInboundTraffic
  expr: rate(node_network_receive_bytes_total{device="eth0"}[1m]) * 8 > 800000000
  for: 2m
```

Netdata charts network throughput on `net.net` per interface, already
as a rate. Translate to a per-interface template scoped to the device:

```text
   template: high_inbound_traffic
         on: net.net
chart labels: device=eth0
     lookup: average -1m unaligned of received
      units: kilobits/s
      every: 10s
       warn: $this > 800000
```

The Prometheus expression converts bytes/s to bits/s; Netdata's
`received` dimension is already kilobits/s, so the threshold is
expressed in the chart's units, not recomputed.

## Worked example 4: instance/endpoint liveness (up == 0)

`up == 0` is Prometheus scrape liveness, not a Netdata metric. Two
targets depending on what "up" meant:

- **An HTTP endpoint**: use the stock `httpcheck` alerts on
  `httpcheck.status` (configure the httpcheck collector to probe the
  target). See [`stock-alert-equivalents.md`](./stock-alert-equivalents.md).
- **A service Netdata collects**: alert when collection stops, using
  the staleness pattern:

```text
   template: myapp_collection_stale
         on: myapp.requests
       calc: $now - $last_collected_t
      units: seconds
      every: 10s
       warn: $this > (5 * $update_every)
       crit: $this > (60 * $update_every)
```

## After translating

Reload and verify on a real engine. Do not trust that the YAML is
correct; load it and confirm it parses, attaches, and evaluates. See
[`verify-migration.md`](./verify-migration.md).

## References

- Health configuration reference: `src/health/REFERENCE.md`.
- PromQL functions: https://prometheus.io/docs/prometheus/latest/querying/functions/
