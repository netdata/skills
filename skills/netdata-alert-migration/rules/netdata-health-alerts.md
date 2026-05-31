# Netdata health alerts: the target DSL

This is the language you translate into. It is concise but unlike
PromQL. Read this before translating. Authoritative source:
`src/health/REFERENCE.md` in the Netdata repo (the grammar below is
verified against the health config parser).

## Entities: alarm vs template

A health file holds one or more entities. The first line is either:

- `alarm: NAME` attaches to one specific chart. `on:` is a chart id,
  e.g. `system.cpu`.
- `template: NAME` attaches to every chart of a context. `on:` is a
  context, e.g. `disk.space`, so it fans out to every disk.

A per-series Prometheus alert (one firing instance per `instance` or
`device` label) almost always becomes a `template:`, because the
context fans the alert across all chart instances automatically.

`NAME` allows alphanumerics, `.`, and `_`. Alarms are processed
before templates of the same name.

## The line keys you will use

| Line | Meaning |
| --- | --- |
| `on:` | chart id (alarm) or context (template) the alert binds to |
| `lookup:` | query a window of the chart's dimensions, result is `$this` |
| `calc:` | arithmetic on `$this` or variables; overwrites `$this` |
| `every:` | evaluation frequency, e.g. `every: 10s` |
| `units:` | display units, e.g. `%`, `items`, `up/down` |
| `warn:` / `crit:` | expressions; non-zero means the alert fires |
| `delay:` | notification delay / flapping control |
| `repeat:` | re-notify interval while raised |
| `info:` | description; supports `${label:NAME}` interpolation |
| `summary:` | short title; same interpolation |
| `to:` | notification role; `to: silent` evaluates but never notifies |
| `host labels:` | scope by host label, e.g. `_os=linux` |
| `chart labels:` | scope by chart label, e.g. `mount_point=/var` |

An entity needs `on:`, and at least one of `lookup`, `calc`, `warn`,
`crit`. If there is no `lookup`, `every:` is required.

## The lookup grammar

```text
lookup: METHOD AFTER [at BEFORE] [every DURATION] [OPTIONS] [of DIMENSIONS] [foreach DIMENSIONS]
```

- **METHOD**: time-aggregation over the window. Common: `average`
  (alias `mean`), `min`, `max`, `sum`, `median`, `stddev`,
  `percentile` (and `percentileNN`), `incremental_sum`. Default `sum`.
- **AFTER**: how far back, a negative duration: `-1m`, `-10m`, `-1h`.
  This is the window length.
- **at BEFORE**: optional window end (default 0 = now). Use to look at
  a past window, e.g. `lookup: min -10m at -50m`.
- **OPTIONS** (space-separated): `absolute` (force positive),
  `percentage` (each dimension as a share of the chart total),
  `unaligned` (do not snap the window to multiples of the duration,
  almost always wanted for alerts), `anomaly-bit` (query the ML
  anomaly rate 0 to 100), `null2zero` (treat gaps as zero),
  `match-names` (match dimensions by name instead of id).
- **of DIMENSIONS**: which dimensions to read, comma or pipe
  separated, patterns allowed. `of all` or omitted reads all
  dimensions. Write `user,system`, not `user, system` (spaces
  separate the list).
- **foreach DIMENSIONS**: fan one definition into one alert per
  matched dimension. If both `of` and `foreach` are given, `of` is
  ignored. The result is `$this`.

`of` aggregates the listed dimensions into one value (one alert).
`foreach` creates one alert per dimension. This is how you reproduce
Prometheus per-label fan-out within a single chart.

## The expression language (calc, warn, crit)

- Arithmetic: `+ - * /`.
- Comparison: `< <= == != <> > >=` (yield 1 or 0; `<>` is `!=`).
- Logical: `&& || !`, and word forms `AND OR NOT`.
- Ternary: `(cond) ? (true_expr) : (false_expr)`.
- Function: `abs()`.
- Special values: `nan` (lookup failed) and `inf` (divide by zero).
  Guard with `($this == nan) ? (nan) : (...)`.

## Variables

- `$this`: this alert's value (result of `calc`, else `lookup`).
- `$status`: this alert's status, compared to `$CLEAR` (1),
  `$WARNING` (2), `$CRITICAL` (3).
- `$now`, `$after`, `$before`: unix timestamps (`$after`/`$before` are
  the lookup window bounds).
- `$last_collected_t`, `$update_every`: last collection time and chart
  frequency (used for the staleness pattern below).
- Each dimension as `$<dimension>` (interpolated) and `$<dimension>_raw`
  (last collected). `$<dim>` is the dimension's last value.
- Another alert on the same chart, by its name (e.g. `$load_cpu_number`).
- A dimension on another chart as `$CHART.dimension`, e.g.
  `$system.ram.used`. For chart ids with `-` or `=` (common in
  Prometheus-derived charts) use the brace form `${chart.dimension}`.

## The hysteresis idiom (the equivalent of stability, not of for)

To stop an alert flapping at the threshold, drop the re-trigger
threshold once raised:

```text
warn: $this > (($status >= $WARNING)  ? (75) : (85))
crit: $this > (($status == $CRITICAL) ? (85) : (95))
```

Once WARNING, the value must fall below 75 to clear. This is the
standard pattern in every stock alert.

## delay and repeat

```text
delay:  [up U] [down D] [multiplier M] [max X]
repeat: [off] [warning DURATION] [critical DURATION]
```

`delay` affects only when the notification is sent, not the alert
state. `delay: up 5m` suppresses a notification until the alert has
been raised for 5 minutes, which is the closest analog to a short
Prometheus `for:`.

## Scoping with labels

```text
host labels: _os=linux
chart labels: mount_point=!/dev !/dev/* *
```

Space-separated `label=pattern` pairs; `*` wildcard, `!` negation,
order matters (first match wins). Multiple labels are ANDed. Use these
to reproduce a PromQL label matcher (`{mountpoint="/var"}` becomes
`chart labels: mount_point=/var`).

## The staleness / "no data" pattern

The closest analog to Prometheus `absent()` or `up == 0` for a metric
Netdata does collect: alert when collection stops.

```text
template: myapp_last_collected
      on: myapp.requests
    calc: $now - $last_collected_t
   every: 10s
    warn: $this > (5 * $update_every)
    crit: $this > (60 * $update_every)
   units: seconds
```

## Loading and reloading

Drop the file in `/etc/netdata/health.d/`, then
`sudo netdatacli reload-health` (no restart). A parse error logs to
the daemon log and the bad entity is skipped, so always verify it
loaded (see [`verify-migration.md`](./verify-migration.md)).

## References

- Health configuration reference: `src/health/REFERENCE.md`.
- Query methods (lookup): `src/web/api/queries/README.md`.
