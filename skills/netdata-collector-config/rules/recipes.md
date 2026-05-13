# Cookbook recipes

The [`netdata/otelcol-cookbook`](https://github.com/netdata/otelcol-cookbook)
repository is the source of truth for end-to-end OpenTelemetry Collector
configurations that target Netdata. Recipes there have been exercised
against a real Netdata Agent and ship complete `otelcol.yaml` files with
inline `TODO` markers where the operator must edit.

When the user asks for a pattern this index lists, fetch the recipe
straight from the cookbook. Do not reconstruct cookbook content here.
The cookbook is updated independently of this skill pack.

## Conventions every recipe uses

- Binary: `otelcol-contrib` from the
  [collector-releases repo][collector-releases]. The contrib
  distribution carries every receiver and processor the recipes
  reference.
- Exporter: `otlp` to `localhost:4317` with `tls.insecure: true`. This
  matches `otel.plugin` listening on the same host. For remote or
  cross-node exporters, swap in the TLS block from
  [`exporters-to-netdata.md`](./exporters-to-netdata.md).
- Debugging: every recipe leaves the `debug` exporter wired in alongside
  `otlp`. Remove `debug` from the pipeline once the recipe is in
  production, or keep it during the bring-up phase.
- Durability: recipes that need to survive Collector restarts use the
  `file_storage` extension to back the exporter's `sending_queue`. See
  [`exporters-to-netdata.md`](./exporters-to-netdata.md) for the same
  pattern documented here.

## Index

- [`syslog-ingest/`][syslog-ingest]: receive RFC 3164 / RFC 5424
  syslog from network devices over UDP, normalize to OpenTelemetry
  semantic conventions, forward to Netdata as OTLP logs.

[collector-releases]: https://github.com/open-telemetry/opentelemetry-collector-releases
[syslog-ingest]: https://github.com/netdata/otelcol-cookbook/tree/master/syslog-ingest

If the user describes a workflow that is not in the index above, check
the cookbook README directly before authoring new config: the index in
this file is refreshed by `scripts/sync-cookbook.py` and may lag the
upstream repo between syncs.

## How to apply a cookbook recipe

1. Identify the recipe directory (for example `syslog-ingest/`).
2. Read the recipe `README.md` end to end. Each `TODO` marker in the
   YAML file corresponds to a decision the operator must make
   (timezone, protocol variant, exporter endpoint).
3. Copy the YAML file into the host that will run the Collector.
4. Edit every `TODO` line.
5. Start the Collector: `otelcol-contrib --config ./otelcol.yaml`.
6. Verify telemetry arrives at Netdata via the MCP integration skill.

## When to write a new recipe instead of editing one

The cookbook recipes are intentionally narrow: one receiver shape per
recipe. If the user needs a composition (for example syslog plus
`hostmetrics` plus `filelog`), build a tailored config from the
modular guidance in [`receivers.md`](./receivers.md),
[`processors.md`](./processors.md), and
[`exporters-to-netdata.md`](./exporters-to-netdata.md). The cookbook is
where the canonical building blocks live; this skill teaches how to
assemble them.
