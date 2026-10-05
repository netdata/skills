# Metric mapping files

## Scope

Control how OTLP metrics become Netdata charts. This is the only
user-facing knob for chart shape; there is no producer-side attribute that
overrides it.

## Where the files go

```text
/etc/netdata/otel.d/v1/metrics/
```

Any `.yaml` file in that directory is loaded. User files override stock
mappings. The plugin ships one stock file (`hostmetrics-receiver.yaml`) that
handles the OTel Collector hostmetrics receiver; everything else falls back
to default behavior until you add a mapping.

## File shape

```yaml
metrics:
  "<otlp.metric.name>":
    - instrumentation_scope:
        name: <regex for scope name, optional>
        version: <regex for scope version, optional>
      dimension_attribute_key: <attribute on the data point, optional>
      interval_secs: <per-metric interval override, optional>
      grace_period_secs: <per-metric grace override, optional>
```

Key points:

- The top-level key is the exact OTLP metric name, including dots. The
  string is not a regex.
- The value is a list. The plugin evaluates entries in order and picks the
  first scope match.
- `instrumentation_scope.name` and `instrumentation_scope.version` are
  regexes, not literals. Anchor them if you need exact match.
- Fields are parsed with `deny_unknown_fields`. A typo (for example
  `dimesion_attribute_key`) causes the whole file to fall back to defaults
  and logs an error.

## Full worked example

Map three metrics from the OTel Collector hostmetrics receiver:

```yaml
metrics:
  "system.network.io":
    - instrumentation_scope:
        name: .*hostmetricsreceiver.*networkscraper$
      dimension_attribute_key: direction

  "system.cpu.utilization":
    - instrumentation_scope:
        name: .*hostmetricsreceiver.*cpuscraper$
      dimension_attribute_key: state

  "system.memory.usage":
    - instrumentation_scope:
        name: .*hostmetricsreceiver.*memoryscraper$
      dimension_attribute_key: state
      interval_secs: 5
      grace_period_secs: 25
```

`dimension_attribute_key: state` tells the plugin: when you see a data
point that carries `attributes.state = "idle"`, turn `idle` into the
dimension name. All data points sharing the other attributes become
dimensions of the same chart.

## How to choose `dimension_attribute_key`

The value must be an attribute that the OTLP producer is already setting on
the data point. Inspect one payload first. The plugin has no raw-payload
capture (the former `store_otlp_json` flag was removed in v2.11.0), so
send the same data through an OTel Collector with a `debug` exporter:

```yaml
exporters:
  debug:
    verbosity: detailed
```

The Collector's own log then prints every data point with its attributes
and instrumentation scope.

Pick an attribute whose cardinality matches how you want the chart split.

## Cardinality guardrail

`metrics.max_new_charts_per_request` (default 100) is a circuit breaker
against high-cardinality attribute values. A producer that flips label
values every request will hit the limit and drop new charts until the
request rate settles.

If you need more than 100 new charts per OTLP request, raise the limit,
but treat that as a sign the dimension key is wrong.

## What "fall back to default" means

Without a matching mapping, the plugin creates charts using its internal
default logic: one chart per unique combination of resource and scope,
with dimension names derived from the metric's type (sum/gauge/histogram)
and any single-value attribute. This is fine for a quick look, poor for
long-lived dashboards. Add a mapping file once you decide the shape.
