# Verifying a collector

A collector is not done until you have confirmed that its charts
exist, have the right shape, and update with sane values. Verify in
two stages: first that the collector emits correct protocol when run
by hand, then that Netdata ingested it.

When a Netdata MCP server is connected, the second stage is automatic.
The agent that built the collector closes the loop itself with MCP
tool calls. Do not stop at "I wrote the collector" and hand the user a
manual checklist. Run the verification, read the result, and report
the confirmed context, dimensions, and a sample value. Only then is
the task done.

## Stage 1: run it standalone

This catches protocol and collection bugs before Netdata is involved.
Do not skip it; it isolates a collection bug from an ingestion bug.

### External plugin (any language)

Run the plugin with the update interval as its only argument:

```bash
/usr/libexec/netdata/plugins.d/myapp.plugin 1
```

You should see the `CHART` and `DIMENSION` block once, then a
`BEGIN` / `SET` / `END` block every second. To reproduce Netdata's
runtime permissions, run it as the `netdata` user:

```bash
sudo -u netdata /usr/libexec/netdata/plugins.d/myapp.plugin 1
```

No output, or a stall, means the bug is in the collector, not in
Netdata. Common causes: stdout not flushed each cycle, an exception
before the first emit, or a value that is not an integer.

### python.d / charts.d module

Run the orchestrator in debug for the one module. The exact
invocation is documented in each plugin's README:
`src/collectors/python.d.plugin/README.md`,
`src/collectors/charts.d.plugin/README.md`.
The debug run prints the same line protocol plus framework log
messages, so you can confirm `get_data()` (Python) or `X_update`
(Bash) returns what you expect.

## Stage 2: confirm ingestion automatically over MCP

This is the end-to-end check, and the agent runs it without waiting
for the user. It needs an MCP connection to the Netdata instance where
the collector runs.

- If a Netdata MCP server is already connected, proceed.
- If not, connect first using the `netdata-mcp-integration` skill. For
  a development loop, connect to the local Agent or Parent
  (`http://HOST:19999/mcp`); that is the most direct path to a
  freshly-installed collector. Netdata Cloud MCP
  (`https://app.netdata.cloud/api/v1/mcp`) also works, provided the
  node running the collector is claimed into the space.

First make sure the agent has had a chance to pick the plugin up:
restart it (`sudo systemctl restart netdata`) or wait one scan cycle,
then run the loop below.

### The automatic verification loop

Native collector metrics are addressed by **context** (for example
`example.twovalues`), not by an OTLP `service.name` attribute. Issue
these as MCP tool calls and read the results:

1. **Context exists.** Call `list_metrics` filtered to the context
   you created. An empty result means the collector is not being
   ingested; jump to "When it does not show up."

   ```text
   Use list_metrics filtered by context "example.twovalues".
   If the result is empty, say so explicitly.
   ```

2. **Shape is correct.** Call `get_metrics_details` for that context.
   Confirm the dimension names match what you defined, the units are
   right, and the chart type (line, area, stacked) is what you
   intended.

   ```text
   Call get_metrics_details for context "example.twovalues".
   List the dimension names, units, and chart type.
   ```

3. **It updates with sane values.** Call `query_metrics` for that
   context over the last 60 seconds. Confirm there is at least one
   data point within the last two collection intervals, that values
   are in the expected range and not uniformly zero, and that any
   dimension you marked `incremental` reads as a rate rather than an
   ever-growing raw counter.

   ```text
   Use query_metrics for context "example.twovalues" over the last
   60 seconds. Report the per-dimension sample count and the latest
   value of each dimension. Fail if the sample count is zero.
   ```

### Pass criteria

All of these must hold before declaring the collector working:

- The context appears in `list_metrics`.
- Dimension names, units, and chart type match the definition.
- `query_metrics` returns points within the last two collection
  intervals (default 1s each unless you set `update_every`).
- Values are plausible: right order of magnitude, counters read as
  rates, fractions are not truncated to zero.

When all pass, report the confirmed context, its dimensions, and a
recent sample value. That is the end-to-end confirmation.

## When it does not show up

Work down this list. If Stage 1 output was correct but `list_metrics`
is empty, the failure is in ingestion, not collection.

- **Plugin not run.** Confirm the file is in `plugins.d`, has the
  executable bit, and has a valid shebang. Confirm it is enabled in
  `netdata.conf` under `[plugins]` (the key is the filename without
  `.plugin`).
- **Plugin disabled by Netdata.** If the plugin exited non-zero or
  printed `DISABLE`, Netdata stopped restarting it. Check the agent
  logs for the plugin name. The plugin's stderr is written to
  Netdata's error log.
- **Module not enabled.** For a `python.d` or `charts.d` module,
  confirm it is enabled in `python.d.conf` / `charts.d.conf` and named
  `<module>.chart.py` / `<module>.chart.sh` in the right directory.
- **Values look wrong, not absent.** A counter charted as a level (or
  the reverse) is an `algorithm` mistake: use `incremental` for
  monotonic counters, `absolute` for levels. Fractions truncated to
  zero mean you sent a non-integer; multiply and set `divisor`.
- **Charts appear then vanish.** A plugin that crashes after the
  first cycle emits definitions, then dies. Check the logs and the
  standalone run for an error after the first `END`.

After any fix, rerun the Stage 2 loop. Iterate until the pass criteria
hold; this is the loop the agent drives on its own.

## Fallback when MCP is not available

If no MCP connection can be established, fall back to the dashboard
(find the chart under its `type` menu and `family` submenu) or the
REST API for a quick check:

```bash
curl -s 'http://localhost:19999/api/v2/contexts' \
  | jq '.contexts | keys[] | select(startswith("example."))'
```

Treat this as a stopgap. The MCP loop is the verification path,
because it lets the agent read the dimensions and values back and
confirm the format without a human in the loop.

## References

- MCP verification patterns and tool inventory: the
  `netdata-mcp-integration` skill, especially `verify-telemetry-flow.md`
  and `query-patterns.md`.
- External plugins API: `src/plugins.d/README.md`.
