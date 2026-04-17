# Redis: Throughput & Latency signals

## Scope

Signals in the Throughput & Latency domain for Redis, as defined in the Netdata operator playbook. Each signal includes a short description, the collection source, and a hint for the MCP query pattern that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Operations Per Second [HIGH]

The instantaneous rate of commands processed per second.

Collection source: `INFO stats` then `instantaneous_ops_per_sec`

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Keyspace Hit Rate [HIGH]

The ratio of successful key lookups to total lookups, indicating cache effectiveness.

Collection source: `INFO stats` then `keyspace_hits` (cumulative counter) `INFO stats` then `keyspace_misses` (cumulative counter) Formula: `hit_rate = keyspace_hits / (keyspace_hits + keyspace_misses)`

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Slow Commands (Slowlog) [HIGH]

The rate of commands exceeding the configured `slowlog-log-slower-than` execution time threshold.

Collection source: `SLOWLOG LEN`; current number of entries in the slow log `SLOWLOG GET <count>`; retrieve recent slow commands with details

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Latency Events [HIGH]

Redis built-in latency monitoring that tracks events where internal operations exceed the configured `latency-monitor-threshold`.

Collection source: `LATENCY LATEST`; most recent sample per event category `LATENCY HISTORY <event>`; time series for a specific event Available since Redis 2.8.13.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Fork Duration [HIGH]

The time in microseconds the main thread was blocked during the most recent `fork()` call.

Collection source: `INFO stats` then `latest_fork_usec`

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

## Triage order within this domain

Investigate HIGH-severity signals first, then MEDIUM, then LOW. HIGH-severity signals have the shortest time to impact; a confirmed HIGH anomaly usually justifies paging. When two HIGH signals move together, treat them as one incident until `find_correlated_metrics` rules out shared cause.

## Common false positives

- A single stale data point from a collector restart triggers many signals briefly. Re-query after 30 seconds before escalating.
- Short bursts under 60 seconds rarely warrant action unless paired with a confirmed business impact.
- Comparing against yesterday's baseline on a post-deploy day produces false anomalies. Compare against the pre-deploy baseline.
- Collector-visible percentile latency with < 100 samples per minute is noise. Require a minimum sample count before acting.

## Remediation pointers

Remediation for signals in this domain is tech-specific and typically covered in the operator playbook's SECTION 3 (Failure Patterns) or SECTION 4 (Runbooks). Before applying a change:

1. Run the MCP verification queries to record the current state.
2. Apply the smallest remediation that addresses the confirmed cause. Config changes before restarts; restarts before rollbacks.
3. Re-run the same MCP queries after the remediation settles. Recording before/after numbers is how a runbook entry gets sharpened over time.

## MCP query examples for this domain

```text
# Pull every signal in this domain at once
query_metrics with contexts=[<signals from the list above>] and relative_window=-30m

# Ask the agent to rank anomalies that match this domain
find_anomalous_metrics filtered by any attribute unique to the Redis service (usually service.name or host.name)

# Look for correlated signals outside this domain
find_correlated_metrics around the incident window, limit 15
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
