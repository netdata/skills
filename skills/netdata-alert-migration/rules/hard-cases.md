# Hard cases: what does not translate

These PromQL constructs have no per-chart equivalent. Do not force
them into a single `lookup`. For each, pick a strategy: a native
Netdata feature, a redesign, collect-first, or a hybrid that keeps
that subset of rules on `vmalert`. A clean hybrid (Netdata for what
maps, `vmalert` for the rest) is a legitimate outcome; say so rather
than inventing a fragile approximation.

## Cross-metric joins

Markers: `a / b` where `a` and `b` are different metrics, `on(...)`,
`ignoring(...)`, `group_left`, `group_right`, and set operators
`and` / `or` / `unless`.

Why it fails: a Netdata alert is bound to one chart context and reads
that chart's dimensions. It cannot join two different metric families.

Strategies, in order of preference:

- **Same chart already.** If the two metrics are dimensions of one
  Netdata chart, the join is just `calc` across dimensions (worked
  example 2 in [`translate-rules.md`](./translate-rules.md)). Many
  ratios that are two metrics in Prometheus are one chart in Netdata.
- **Stock ratio.** Netdata often charts the ratio directly (cache hit
  ratio, error ratio). Check
  [`stock-alert-equivalents.md`](./stock-alert-equivalents.md).
- **Cross-chart variables.** For two specific named charts, reference
  the other chart's dimension as `$CHART.dimension` (e.g.
  `$system.ram.used`) in `calc`. This works for fixed chart ids, not
  for `template` fan-out across instances.
- **Keep on vmalert** if the join is across high-cardinality instances
  matched by label. This is the honest answer for genuine multi-metric
  label joins.

## Forecasting

Markers: `predict_linear`, `deriv`, `holt_winters` /
`double_exponential_smoothing`.

Why it fails: `lookup` aggregates a fixed window; it does not
extrapolate.

Strategies:

- **Native disk-fill prediction.** The most common forecasting rule
  (`predict_linear` on filesystem space) has a stock equivalent,
  `out_of_disk_space_time`. Reproduce other forecasts with the same
  two-step pattern it uses: lookup a past window to derive a fill
  rate, then `calc` the time-to-threshold.

```text
   template: myapp_fill_rate
         on: myapp.storage
     lookup: min -10m at -50m unaligned of avail
       calc: ($this - $avail) / (($now - $after) / 3600)
   template: myapp_out_of_space_time
         on: myapp.storage
       calc: ($myapp_fill_rate > 0) ? ($avail / $myapp_fill_rate) : (inf)
      units: hours
       warn: $this > 0 AND $this < 48
       crit: $this > 0 AND $this < 24
```

- **Rate-of-change threshold.** For non-storage forecasts, alert on a
  steep rate of change instead of a projection.
- **Keep on vmalert** if the forecast is essential and has no
  rate-based proxy.

## Histogram quantiles

Markers: `histogram_quantile`, `quantile_over_time` over `_bucket`
series.

Why it fails: it needs every `le` bucket of a histogram aligned and
interpolated, which is not a single-chart dimension reduction.

Strategies:

- **Alert on a precomputed quantile.** If the producer also exposes a
  summary/quantile metric, or the Netdata collector charts a
  percentile dimension, alert on that with a plain `lookup`.
- **lookup percentile** on a chart that holds raw per-event samples
  (`lookup: percentile95 -5m`). This works only when the chart stores
  the distribution, not pre-bucketed counts.
- **Keep on vmalert** for true bucket-based histogram quantiles.

## Fleet aggregation and ranking

Markers: `sum`/`avg`/`count`/`min`/`max by(...)`, `topk`, `bottomk`,
and quorum conditions like `count(up == 0) > 2`.

Why it fails: Netdata attaches an alert to each chart instance and
fires per node. A single expression that collapses or ranks across the
fleet has no per-chart form.

Strategies:

- **Per-instance is often what you want.** "Any node over 90%"
  becomes a `template` that fires on each node individually. This is
  usually more actionable than the fleet aggregate.
- **Aggregate at a Parent.** A Netdata Parent receiving many children
  can host alerts on aggregate charts where they exist.
- **Cloud for fleet view.** Netdata Cloud shows fleet-wide alert state
  across nodes.
- **Keep on vmalert** for genuine quorum or top-N conditions (e.g.
  "more than 2 of N replicas down"). This is a real gap; flag it.

## Absence and scrape liveness

Markers: `absent()`, `absent_over_time()`, `up == 0`.

Why it fails: a value-threshold engine has nothing to evaluate when a
series is absent.

Strategies:

- **Collected metric stopped.** Use the staleness pattern
  (`$now - $last_collected_t`) from
  [`netdata-health-alerts.md`](./netdata-health-alerts.md).
- **Endpoint/port liveness.** Use the stock `httpcheck` / `portcheck`
  / `ping` collectors and their stock alerts.
- **A metric that should exist but never appeared.** Netdata cannot
  alert on a chart that was never created. Add a liveness collector or
  keep this on vmalert.

## Subqueries and nested rollups

Markers: `max_over_time(rate(m[5m])[30m:1m])`.

Why it fails: `lookup` is a single window; it does not nest.

Strategy: flatten to one window if the intent allows (often the outer
window is what matters), otherwise keep on vmalert.

## Recording the gaps

Whatever stays on `vmalert`, list it explicitly with the reason. A
migration that honestly reports "these 4 quorum rules remain on
vmalert" is correct; one that silently drops them is not.

## References

- PromQL operators: https://prometheus.io/docs/prometheus/latest/querying/operators/
- Stock disk-fill alert: `src/health/health.d/disks.conf` in the Netdata repo.
