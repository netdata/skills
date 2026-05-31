# StatsD ingestion

Netdata ships a built-in StatsD server. Applications push metrics to
it; Netdata charts them. No collector code. This is the right path
when metrics originate inside your application and you want push
rather than scrape, especially on a hot path, since StatsD is
non-blocking over UDP.

Source: Netdata is a "fully-featured statsd server," default port
8125, both UDP and TCP.
`src/collectors/statsd.plugin/README.md`.

## How apps send metrics

The wire format is one metric per line:

```text
name:value|type|@samplerate
```

`@samplerate` is optional. Netdata supports seven metric types:

| Type | Suffix | Notes |
| --- | --- | --- |
| Gauge | `g` | latest value; supports increment/decrement |
| Counter | `c` / `C` | `:value` optional, defaults to 1 |
| Meter | `m` | rate-focused counter |
| Timer | `ms` | min/max/avg/percentiles/median/stddev/count |
| Histogram | `h` | distribution statistics |
| Set | `s` | count of unique values; text values |
| Dictionary | `d` | counts per distinct value; text values |

Send one metric from the shell over UDP:

```sh
echo "myapp.used_memory:123456|g" | nc -u -w 0 localhost 8125
```

Over TCP each metric must end with a newline so Netdata can split
metrics across packets; with UDP keep each datagram under the network
MTU. StatsD client libraries exist for most languages (Python, Node,
Java, Go, Ruby, shell).

## Default binding is localhost only

By default Netdata binds StatsD to localhost:

```text
[statsd]
    # default port = 8125
    # bind to = udp:localhost:8125 tcp:localhost:8125
```

For applications on other hosts, change `bind to` in `netdata.conf`
to a routable address. Source:
`src/collectors/statsd.plugin/README.md`.

## Private charts vs synthetic charts

- **Private charts** are auto-generated, one per incoming metric, no
  config. Controlled by `create private charts for metrics matching`
  (a space-separated pattern list, default `*`). A safety cap,
  `max private charts hard limit` (default 1000), bounds them.
- **Synthetic charts** are charts you define that combine several
  StatsD metrics into a curated dashboard section, with the family,
  context, and units you choose. Define them in the `statsd.d/`
  config directory, one `<app>.conf` per application.

These config files are INI-style, not YAML. Do not confuse them with
go.d job files.

## Synthetic chart config

A full example, one app with one chart of two dimensions. Source:
`src/collectors/statsd.plugin/README.md`.

```text
[app]
	name = myapp
	metrics = myapp.*
	private charts = no
	gaps when not collected = no
	history = 60

[dictionary]
	m1 = metric1
	m2 = metric2

# Chart id is 'mychart'; the chart is named myapp.mychart
[mychart]
	name = mychart
	title = my chart title
	family = my family
	context = chart.context
	units = tests/s
	priority = 91000
	type = area
	dimension = myapp.metric1 m1
	dimension = myapp.metric2 m2
```

`[app]` section keys (all documented in the README):

- `name`: application name; charts are grouped under it.
- `metrics`: a pattern matching every metric for this app.
- `private charts`: `yes`/`no`, auto-charts for matched metrics.
- `gaps when not collected`: `yes`/`no`, show gaps on silence.
- `memory mode` and `history`: optional, override storage for this
  app's charts.

`[dictionary]` maps raw metric names to readable dimension names. It
can be empty or omitted.

Each `[chartid]` section defines one synthetic chart named
`app_name.chartid`, with `name`, `title`, `family` (submenu),
`context` (drives alert templates), `priority`, `type` (`line`,
`area`, or `stacked`), `units`, and one or more `dimension` lines.

The dimension line format:

```text
dimension = [pattern] METRIC NAME TYPE MULTIPLIER DIVIDER OPTIONS
```

`METRIC` is the collected name (must match the app `metrics`
pattern), `NAME` is the display name (dictionary-resolvable), `TYPE`
selects which value to plot for timers/histograms (`events`, `last`,
`min`, `max`, and so on). `MULTIPLIER`, `DIVIDER`, and `OPTIONS`
(for example `hidden`) are optional.

## When this is the right choice

- The app already emits StatsD, or you control the code and want push
  without writing or maintaining a collector.
- The metric is produced on a latency-sensitive path; StatsD over UDP
  adds almost no overhead.
- You want millions of metrics per second on a single core with no
  extra daemon.

## When to look elsewhere

- You cannot modify the app and it does not speak StatsD. You need a
  collector that reaches out to it. See
  [`external-plugin-protocol.md`](./external-plugin-protocol.md).

## References

- StatsD plugin README:
  `src/collectors/statsd.plugin/README.md`
