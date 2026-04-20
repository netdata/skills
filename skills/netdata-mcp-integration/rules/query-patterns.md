# MCP query patterns

## Tool inventory

Netdata exposes 13 MCP tools. The wire names are:

| Tool | Purpose |
|---|---|
| `list_metrics` | Discover available metrics, optionally filtered. |
| `get_metrics_details` | Fetch dimension/instance metadata for one or more contexts. |
| `list_nodes` | Enumerate monitored nodes visible to this Netdata. |
| `get_nodes_details` | Resource and metadata about specific nodes. |
| `list_functions` | Discover on-demand diagnostic functions per node. |
| `execute_function` | Run a diagnostic or control function on a node (side-effecting). |
| `query_metrics` | Return numeric time-series data points. |
| `find_correlated_metrics` | Rank metrics by co-movement around an incident. |
| `find_anomalous_metrics` | Rank metrics by anomaly rate. |
| `find_unstable_metrics` | Rank metrics by variability. |
| `list_raised_alerts` | Currently firing alerts. |
| `list_running_alerts` | All alerts in a running state (includes CLEAR). |
| `list_alert_transitions` | History of alert state changes. |

There is no `list_configured_alerts`. If an agent asks for that name,
steer it to `list_running_alerts`.

## Common prompt shapes

### "What is happening on node X right now?"

```text
1. list_nodes to confirm node X is reachable.
2. get_nodes_details for node X.
3. list_raised_alerts for node X.
4. find_anomalous_metrics for node X in the last 15 minutes.
Summarize.
```

### "Did my new instrumentation actually arrive?"

```text
1. list_metrics with filter service.name="<service>".
2. For the first three contexts returned, query_metrics for the last
   60 seconds.
3. Report the per-context sample counts.
```

### "Why is service X slow?"

```text
1. list_metrics filtered by service.name="<service>".
2. query_metrics for latency-related contexts (http.server.duration,
   rpc.server.duration) over the last 30 minutes.
3. find_correlated_metrics around the slowest window to find the
   infrastructure signals (CPU, I/O, DB) that moved with it.
```

### "Show me hosts with unusual CPU"

```text
find_anomalous_metrics filtered by context prefix system.cpu, limit
10, over the last 30 minutes.
```

## Writing reliable tool arguments

- Time ranges: pass absolute RFC3339 timestamps or relative strings
  like `-15m`. The agent usually picks sensibly; nudge it toward
  shorter windows for fast iteration.
- Filters: use OpenTelemetry resource attribute names (`service.name`,
  `host.name`, `deployment.environment`) when querying data that
  originated from OTLP producers. For Netdata-native plugin metrics,
  dimensions are named differently; use `list_metrics` to discover.
- Limits: cap `find_*` calls at 10 to 25 results. Higher limits often
  exceed the agent's context budget.

## Side-effecting tool: `execute_function`

`execute_function` runs a named function on a specific node. The
catalog depends on what collectors/functions are loaded. Examples:
`mysql-processlist`, `systemd-list-units`, `network-connections`.

Treat every `execute_function` call the same as a shell command:

- Confirm it is read-only (most are) before approving.
- Constrain the node list. A function that lists processes is cheap
  per node; running it across a 1000-node fleet is not.
- Inspect the response size. Some function outputs are large enough
  to blow past the agent's context.

## What MCP does not do

- No write access to alert configuration.
- No ad-hoc new collectors at runtime.
- No modification of Netdata config files.
- No arbitrary SQL or code execution on the host.

For anything that mutates state beyond `execute_function`, fall back
to SSH + `netdatacli` or the config-editing flow of the target
service.
