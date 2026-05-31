---
name: netdata-custom-collector
description: Use when you need Netdata to collect metrics from something it does not already monitor, such as a custom application, an internal service, the output of a script or CLI tool, or a device. Covers the decision tree from the built-in StatsD server (zero collector code) through writing a collector in any language via the external-plugin line protocol (CHART/DIMENSION/BEGIN/SET/END on stdout), or the legacy python.d and charts.d module frameworks. Teaches how to pick the cheapest approach that works, scaffold it from a real example, and, when a Netdata MCP server is connected, automatically verify over MCP that the metrics are collected in the right format without user handholding.
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - collectors
  - statsd
  - bash
  - python
  - external-plugins
---

# Netdata custom collector

This skill gets metrics into Netdata from a target it does not yet
monitor. The target can be an application you wrote, a third-party
service with no stock collector, a CLI tool whose output you want
charted, or a device behind a script.

Netdata is a pull-and-local-collection system. A collector runs on
the node, gathers values on an interval, and emits charts. This is a
different path from the OTLP push path covered by
`netdata-instrumentation` and `netdata-otel-setup`. If the target is
your own code and you are willing to add an OpenTelemetry SDK, prefer
those skills. Reach for a collector when you cannot or do not want to
instrument the target, or when the data lives in a file, socket, API,
or command rather than in your application's call path.

## When to use this skill

- The user wants to monitor an application or service Netdata does
  not list among its existing integrations.
- The user has a script, exporter, or CLI tool whose numbers they
  want charted and alerted in Netdata.
- The user asks "how do I write a Netdata collector" in Python, Bash,
  or "any language."
- The user already emits StatsD, or can add a few StatsD client calls,
  and wants Netdata to read it.
- The user is extending or fixing an existing `python.d` or
  `charts.d` module.

## Key facts

- Always answer the cheaper question first: does Netdata already have
  a collector for this target? Netdata ships 800+ integrations. Check
  the catalog before writing anything. See
  [`rules/choose-an-approach.md`](./rules/choose-an-approach.md).
- The preference order, cheapest first:
  1. **Existing collector.** Configure it. No code.
  2. **StatsD.** If the app speaks StatsD, or you can add a few
     client calls, push to Netdata's built-in StatsD server on port
     8125. Zero collector code. See [`rules/statsd.md`](./rules/statsd.md).
  3. **Write a collector.** Only when collection needs custom logic.
- When you must write a collector, pick the framework by constraint,
  not by taste:
  - **Any language via the external-plugin line protocol.** This is
    the default. A plugin is any executable that prints
    `CHART`/`DIMENSION`/`BEGIN`/`SET`/`END` to stdout. Write it in
    Bash, Python, Go, Ruby, Node, or whatever fits, including wrapping
    a CLI tool or a library that only exists in one language. See
    [`rules/external-plugin-protocol.md`](./rules/external-plugin-protocol.md).
  - **`python.d` / `charts.d`** are the legacy orchestrated module
    frameworks (Python and Bash). Use them to extend an existing
    module; do not start new collectors there. See
    [`rules/python-and-bash-modules.md`](./rules/python-and-bash-modules.md).
- Netdata's first-party framework, `go.d` (Go), produces the most
  efficient collectors but a module must be compiled into the
  `go.d.plugin` binary from the Netdata Go source. That build-from-
  source workflow is out of scope for this skill; for a production or
  contributable Go collector, follow the official go.d developer
  guide. For a Go collector you only want to run locally, write it as
  an external plugin (above) instead.
- Netdata states it uses Go as the platform of choice for collectors
  and generally does not accept new Python modules into the core
  repo; community Python and Bash modules go to
  [`netdata/community`](https://github.com/netdata/community). Source:
  `docs/developer-and-contributor-corner/python-collector.txt`.
- Every framework ultimately emits the same chart model: a chart has
  a `context` (its template), a `family` (dashboard submenu), and
  dimensions, each with an algorithm (`absolute` for a level,
  `incremental` for a counter). The line protocol in
  [`rules/external-plugin-protocol.md`](./rules/external-plugin-protocol.md)
  is the canonical reference for these fields; the higher-level
  frameworks are conveniences over it.
- When a Netdata MCP server is connected, verification is automatic.
  The agent that built the collector confirms it end to end by calling
  the MCP tools (`list_metrics`, `get_metrics_details`,
  `query_metrics`) itself: it checks the context exists, the
  dimensions and units and chart type match, and recent samples are
  sane. Do not write the collector and then hand the user a manual
  checklist. Close the loop. See
  [`rules/verify-a-collector.md`](./rules/verify-a-collector.md) and
  the `netdata-mcp-integration` skill.

## Step-by-step

1. **Rule out writing code.** Walk the decision tree in
   [`rules/choose-an-approach.md`](./rules/choose-an-approach.md):
   existing collector, then StatsD. Stop at the first that fits.
2. **If the app can push StatsD**, configure ingestion and optional
   synthetic charts per [`rules/statsd.md`](./rules/statsd.md), then
   skip to verification.
3. **If you must write a collector**, choose the framework:
   - Any language (the default): external-plugin protocol. Follow
     [`rules/external-plugin-protocol.md`](./rules/external-plugin-protocol.md).
   - Touching an existing `python.d`/`charts.d` module: follow
     [`rules/python-and-bash-modules.md`](./rules/python-and-bash-modules.md).
5. **Verify** end to end. Run the collector standalone to catch
   protocol bugs, then confirm ingestion. If a Netdata MCP server is
   connected, do this automatically: call `list_metrics`,
   `get_metrics_details`, and `query_metrics` to confirm the context,
   shape, and live values, and iterate until they pass. If no MCP
   connection exists, set one up first via the
   `netdata-mcp-integration` skill. See
   [`rules/verify-a-collector.md`](./rules/verify-a-collector.md).

## Common mistakes

- Writing a collector when a stock one exists. Search the catalog
  first. The most common "missing" collector is already shipped under
  a different name.
- Starting a brand-new collector as a `python.d` or `charts.d`
  module. Those frameworks are legacy and mostly superseded by go.d.
  For a new collector, write a raw external plugin in any language and
  reserve `python.d`/`charts.d` for extending an existing module.
- Emitting fractional values through the line protocol. `SET` takes
  integers only. Multiply in code and set the dimension `divisor`.
- Forgetting to flush stdout each cycle in an external plugin. The
  pipe buffers, and Netdata sees nothing.
- Putting a custom plugin somewhere other than the `plugins.d`
  directory, or shipping it without the executable bit. Netdata only
  runs executables it finds in `plugins.d`.
- Declaring the collector done after writing it, without confirming
  Netdata actually charted the metrics. When an MCP connection is
  available, the agent verifies this itself rather than asking the
  user to open the dashboard.

## Verification

Confirm the collector works before declaring victory, in two stages.

First, run the collector standalone and read its protocol output, to
isolate collection bugs from ingestion bugs. For an external plugin,
run it with the update interval as its only argument and read the
emitted `CHART`/`DIMENSION`/`BEGIN`/`SET`/`END` lines.

Second, confirm Netdata ingested it. When a Netdata MCP server is
connected, the agent does this automatically rather than handing it
off: `list_metrics` to confirm the context exists,
`get_metrics_details` to confirm dimensions, units, and chart type,
and `query_metrics` to confirm recent samples are present and sane.
Iterate on the collector until those pass. If no MCP connection
exists, set one up via the `netdata-mcp-integration` skill, or fall
back to the dashboard or REST API as a stopgap. The full procedure and
pass criteria are in
[`rules/verify-a-collector.md`](./rules/verify-a-collector.md).

## References

- [`rules/choose-an-approach.md`](./rules/choose-an-approach.md)
- [`rules/statsd.md`](./rules/statsd.md)
- [`rules/external-plugin-protocol.md`](./rules/external-plugin-protocol.md)
- [`rules/python-and-bash-modules.md`](./rules/python-and-bash-modules.md)
- [`rules/verify-a-collector.md`](./rules/verify-a-collector.md)
- Netdata integrations catalog: https://www.netdata.cloud/integrations/
- Monitor anything: https://learn.netdata.cloud/docs/data-collection/monitor-anything
- External plugins API: `src/plugins.d/README.md`
