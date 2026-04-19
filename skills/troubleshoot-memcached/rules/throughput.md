# Memcached: Throughput signals

## Scope

Signals in the Throughput domain for Memcached, as defined in the Netdata operator playbook. Each
signal includes a short description, the collection source, and a hint for the MCP query pattern
that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Command Rates (cmd_get, cmd_set, cmd_touch) [MED]

The rate of each command type processed by memcached. These are cumulative counters; derive rates by
computing deltas.

Collection source: `stats` command then fields `cmd_get`, `cmd_set`, `cmd_touch`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Flush All Events (cmd_flush) [MED]

The number of `flush_all` commands executed. Each `flush_all` invalidates ALL cached data; it is a
destructive administrative action.

Collection source: `stats` command then field `cmd_flush` (cumulative counter).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Network Byte Throughput (bytes_read, bytes_written) [MED]

Total bytes read from and written to the network across all connections.

Collection source: `stats` command then fields `bytes_read`, `bytes_written` (cumulative, network
I/O bytes).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

## Triage order within this domain

Investigate HIGH-severity signals first, then MEDIUM, then LOW. HIGH-severity signals have the
shortest time to impact; a confirmed HIGH anomaly usually justifies paging. When two HIGH signals
move together, treat them as one incident until `find_correlated_metrics` rules out shared cause.

## Common false positives

- A single stale data point from a collector restart triggers many signals briefly. Re-query after
  30 seconds before escalating.
- Short bursts under 60 seconds rarely warrant action unless paired with a confirmed business
  impact.
- Comparing against yesterday's baseline on a post-deploy day produces false anomalies. Compare
  against the pre-deploy baseline.
- Collector-visible percentile latency with < 100 samples per minute is noise. Require a minimum
  sample count before acting.

## Remediation pointers

Remediation for signals in this domain is tech-specific and typically covered in the operator
playbook's SECTION 3 (Failure Patterns) or SECTION 4 (Runbooks). Before applying a change:

1. Run the MCP verification queries to record the current state.
2. Apply the smallest remediation that addresses the confirmed cause. Config changes before
   restarts; restarts before rollbacks.
3. Re-run the same MCP queries after the remediation settles. Recording before/after numbers is how
   a runbook entry gets sharpened over time.

## Netdata contexts that surface Throughput

These are the real Netdata chart contexts the native collector emits for Memcached. Use these names
verbatim in `query_metrics` calls.

- `memcached.get`: Get Requests (requests). Dimensions: hints, misses.
- `memcached.get_rate`: Get Request Rate (requests/s). Dimensions: rate.
- `memcached.set_rate`: Set Request Rate (requests/s). Dimensions: rate.
- `memcached.delete`: Delete Requests (requests). Dimensions: hits, misses.
- `memcached.cas`: Check and Set Requests (requests). Dimensions: hits, misses, bad value.
- `memcached.increment`: Increment Requests (requests). Dimensions: hits, misses.
- `memcached.decrement`: Decrement Requests (requests). Dimensions: hits, misses.
- `memcached.touch`: Touch Requests (requests). Dimensions: hits, misses.
- `memcached.touch_rate`: Touch Request Rate (requests/s). Dimensions: rate.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[memcached.get, memcached.get_rate, memcached.set_rate, memcached.delete, memcached.cas, memcached.increment] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="memcached.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="memcached.get"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
