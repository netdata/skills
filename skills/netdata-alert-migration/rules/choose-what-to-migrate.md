# Choosing what to migrate

Run every source rule through this tree before writing anything. Most
of the value is in not translating rules that Netdata already covers
or that cannot be reproduced as-is.

## Step 0: split alerting rules from recording rules

A Prometheus/vmalert rule file is a list of `groups`, each with
`rules`. A rule with an `alert:` key is an alerting rule; one with a
`record:` key is a recording rule.

- **Recording rules**: drop them. They precompute expressions and
  write them back as new series for performance. Netdata evaluates
  alerts at the source against raw charts, so the precomputation layer
  is unnecessary. The one exception: if an alerting rule's `expr`
  references a recorded metric (a `level:metric:operations` name),
  inline the recording rule's `expr` into the alert before
  translating. Source:
  https://prometheus.io/docs/prometheus/latest/configuration/recording_rules/
- **Alerting rules**: classify each with the steps below.

## Step 1: does Netdata already ship this alert?

Netdata ships 137 stock health files. The common node_exporter and
exporter alerts almost all have a stock equivalent already attached to
the right context. Check
[`stock-alert-equivalents.md`](./stock-alert-equivalents.md) first.

If a stock alert covers the signal, do not translate. Enable or tune
it (usually a one-line `to:` change plus a threshold tweak in a
drop-in under `/etc/netdata/health.d/`). This is the outcome for the
majority of a typical infrastructure rule set: CPU, memory, OOM, disk
space and inodes, disk fill prediction, load, file descriptors,
certificate expiry, ping and HTTP liveness, MySQL, PostgreSQL, Redis,
Kubernetes, and 5xx rates.

## Step 2: does Netdata collect the metric this rule needs?

A Netdata alert can only attach to a chart context that exists. Find
the context and dimensions that carry the data the rule's `expr`
references.

- If Netdata collects it (natively, via a collector, or via OTLP),
  note the context and dimension names. You will need them for the
  `on:` and `lookup ... of` lines.
- If Netdata does not collect it, the alert cannot be reproduced yet.
  Either collect the metric first (use the `netdata-custom-collector`
  skill) or keep that rule on `vmalert` until the metric is available.
  Do not write an alert against a context that does not exist; it will
  parse but never attach.

## Step 3: does the expression translate cleanly?

A rule translates cleanly when it is a single metric compared to a
threshold, optionally with simple arithmetic on that one metric, and a
`for:` duration. Examples: `myapp_queue_depth > 1000`,
`100 - (mem_avail / mem_total * 100) > 90` (single chart, percentage
dimension), `rate(myapp_errors_total[5m]) > 10`.

These map to a Netdata `template:`/`alarm:` with `lookup` over a
window, optional `calc`, and `warn:`/`crit:`. Follow
[`translate-rules.md`](./translate-rules.md).

## Step 4: is it a hard case?

A rule is a hard case when its expression is fundamentally
multi-series, cross-metric, forecasting, or existence-based. Markers:

- Vector matching: `on(...)`, `ignoring(...)`, `group_left`,
  `group_right`, or set operators `and`/`or`/`unless`.
- Forecasting: `predict_linear`, `deriv`, `holt_winters` /
  `double_exponential_smoothing`.
- Distribution: `histogram_quantile`, `quantile_over_time`.
- Fleet aggregation or ranking: `sum`/`avg`/`count`/`min`/`max by(...)`,
  `topk`, `bottomk`, `count(up == 0) > N`.
- Existence: `absent()`, `absent_over_time()`, `up == 0`.

Do not force these into a single `lookup`. Apply the matching strategy
in [`hard-cases.md`](./hard-cases.md): a native Netdata equivalent
(several exist, for example disk-fill prediction), a redesign to a
per-chart alert, collect-first, or keep the rule on `vmalert`.

## The classification, summarized

| Rule shape | Outcome | Rule file |
| --- | --- | --- |
| Common infra signal | Enable/tune stock alert | `stock-alert-equivalents.md` |
| Metric not in Netdata | Collect first, or keep on vmalert | `netdata-custom-collector` skill |
| Single metric vs threshold | Translate | `translate-rules.md` |
| Join / forecast / histogram / fleet / absent | Strategy per case | `hard-cases.md` |
| Recording rule | Drop, or inline into an alert | (this file, Step 0) |

Produce an explicit list of which rules landed in each bucket. Name
any rule that cannot be reproduced and why; do not silently omit it.

## References

- Recording vs alerting rules:
  https://prometheus.io/docs/prometheus/latest/configuration/recording_rules/
- Netdata stock health library: `src/health/health.d/` in the Netdata repo.
