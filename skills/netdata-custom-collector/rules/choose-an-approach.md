# Choosing how to collect

Pick the cheapest path that actually fits. Each step down this tree
costs more effort to build and maintain than the one above it. Stop
at the first match.

## Step 0: does a collector already exist?

Netdata ships hundreds of collectors. Writing one for a target that
is already supported is the most common wasted effort.

- Search the integrations catalog:
  https://www.netdata.cloud/integrations/
- Or grep the in-repo list:
  `src/collectors/COLLECTORS.md`.
- The "Monitor anything" page is the canonical entry point:
  https://learn.netdata.cloud/docs/data-collection/monitor-anything

If a collector exists, configure it (`sudo ./edit-config
go.d/<name>.conf` for go.d modules) and stop. The rest of this skill
does not apply.

Watch for targets that are supported under a different name. A
service is often covered by a generic collector (an HTTP endpoint, a
Prometheus exporter, a log file) even when there is no collector
named after the product.

## Step 1: can the app push StatsD?

Netdata has a built-in StatsD server. If your application already
emits StatsD, or you control the code and can add a few client calls,
push metrics to UDP/TCP port 8125. Netdata charts every metric
automatically (private charts) and you can curate dedicated dashboard
sections with synthetic charts defined in a config file. No collector
code, and StatsD clients exist for most languages.

Choose StatsD over a custom collector when the data originates inside
your app on a hot path. StatsD is push and non-blocking, so it adds
almost no latency to the application.

Go to [`statsd.md`](./statsd.md).

Source: Netdata ships a "fully-featured statsd server," default port
8125, UDP and TCP.
`src/collectors/statsd.plugin/README.md`.

## Step 2: write a collector

You are here only because collection needs custom logic: hitting a
private API, parsing a file or command output, talking a bespoke
protocol, or computing values the target does not expose directly.
Pick the framework by constraint.

### Any language via the external-plugin protocol

This is the default for a custom collector. A plugin is any
executable that prints the chart line protocol to stdout. It is the
universal escape hatch: if you can print text on an interval, you can
feed Netdata. Write it in Bash, Python, Go, Ruby, Node, or whatever
fits, including a library that only exists in one language (a vendor
SDK, a gem, a client) or a wrapper around an existing CLI tool.

The trade-off is operational: the node must have that language's
runtime, and a slow plugin only slows itself (each plugin is its own
process).

Go to [`external-plugin-protocol.md`](./external-plugin-protocol.md).

Source: `plugins.d` "collects metrics from external processes,"
reading the line protocol from the plugin's stdout.
`src/plugins.d/README.md`.

### `python.d` / `charts.d` for existing modules only

These orchestrated frameworks host Python and Bash modules so you
write only the collect-and-return logic, not the raw protocol or your
own process loop. They are legacy: most former Python and Bash
modules have been replaced by go.d equivalents, and Netdata steers
new core contributions to Go.

Use them when you are extending or fixing a module that already lives
in one of these frameworks, or contributing a community module that
leans on a language-specific library. For a brand-new standalone
collector, prefer a raw external plugin.

Go to [`python-and-bash-modules.md`](./python-and-bash-modules.md).

### Out of scope: the go.d Go framework

Netdata's first-party collector framework is `go.d` (Go). It produces
the most efficient collectors and adds no runtime dependency to the
node, but a module is several files of framework wiring and must be
compiled into the `go.d.plugin` binary from the Netdata Go source.
That build-from-source workflow is out of scope for this skill. When
you want a production-grade, contributable Go collector, follow the
official guide:
https://learn.netdata.cloud/docs/developer-and-contributor-corner/external-plugins/go.d.plugin.
For a Go collector you just want to run locally, an external plugin
written in Go (Step 2 above) is the lighter path and needs no rebuild
of Netdata.

## Quick reference

| Situation | Approach | Code? |
| --- | --- | --- |
| Target already supported | Configure stock collector | None |
| App emits / can emit StatsD | Built-in StatsD server | Client calls only |
| Custom logic, any language | External-plugin protocol | Any-language script |
| Extending an existing module | `python.d` / `charts.d` | Python / Bash module |
| Production / contributable Go module | go.d framework (see official guide) | Out of scope here |
