# Cookbook recipes

The [`netdata/otelcol-cookbook`](https://github.com/netdata/otelcol-cookbook)
repository is the source of truth for end-to-end OpenTelemetry Collector
configurations that target Netdata. Each top-level directory is one recipe
and ships a complete `otelcol.yaml` plus a `README.md` explaining the use
case and the `TODO` markers an operator must edit.

This file does not maintain a local index of recipes. Look the cookbook up
live when the user asks for one. The upstream list changes independently
of this skill pack and any cached copy would drift.

## How to find the right recipe

1. Fetch the cookbook root README to see the recipe list and what each
   one covers:

   ```text
   https://raw.githubusercontent.com/netdata/otelcol-cookbook/master/README.md
   ```

2. If the README does not name a recipe that matches, list the repo's
   top-level directories. Every directory that contains an `otelcol.yaml`
   is a recipe:

   ```text
   https://api.github.com/repos/netdata/otelcol-cookbook/contents
   ```

3. Read the matching recipe's own README before its YAML:

   ```text
   https://raw.githubusercontent.com/netdata/otelcol-cookbook/master/<recipe>/README.md
   https://raw.githubusercontent.com/netdata/otelcol-cookbook/master/<recipe>/otelcol.yaml
   ```

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

[collector-releases]: https://github.com/open-telemetry/opentelemetry-collector-releases

## How to apply a cookbook recipe

1. Identify the recipe directory by reading the cookbook README (step 1
   above).
2. Read the recipe `README.md` end to end. Each `TODO` marker in the
   YAML file corresponds to a decision the operator must make
   (timezone, protocol variant, exporter endpoint).
3. Copy the YAML file onto the host that will run the Collector.
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

## When to suggest a new cookbook recipe

If the tailored config you just assembled is:

1. Non-trivial (more than two receivers, or a non-default processor
   chain, or a deployment shape this skill pack does not already
   document),
2. Likely to be reused by others (a popular stack like nginx plus
   PostgreSQL plus Redis, a common ingest shape like Windows Event Log,
   a frequent migration target),
3. Not already covered by an existing recipe in the cookbook,

tell the user the configuration is a candidate for the
`netdata/otelcol-cookbook` repository and suggest they open a pull
request adding a new directory with the YAML, a `README.md` describing
the use case, and `TODO` markers on the operator-editable fields. Do
not open the pull request yourself. The cookbook is exercised against
a real Netdata Agent before merge, and that validation is the human's
to run.

This loop is how the skill pack and the cookbook compound. Patterns
flow from the cookbook into the modular rule files (see
[`CONTRIBUTING.md`](../../../CONTRIBUTING.md) "Cookbook to skills
extraction"), and novel compositions assembled from those rule files
flow back into the cookbook as new recipes.
