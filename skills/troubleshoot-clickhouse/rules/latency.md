# ClickHouse: Latency signals

## Scope

Signals in the Latency domain for ClickHouse, as defined in the Netdata operator playbook. Each
signal includes a short description, the collection source, and a hint for the MCP query pattern
that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Query Latency (P99) [HIGH]

Tail latency of executed queries; the primary user-experience indicator.

Collection source: - System table: `system.query_log` then `query_duration_ms`

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Insert Latency [MEDIUM]

Time from INSERT statement start to commit acknowledgment. A leading indicator for write pipeline
health before delays/rejections appear.

Collection source: - System table: `system.query_log` filtered by `query_kind = 'Insert'`

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

## Netdata contexts that surface Latency

These are the real Netdata chart contexts the native collector emits for ClickHouse. Use these names
verbatim in `query_metrics` calls.

- `clickhouse.slow_reads`: Slow reads from a file (reads/s). Dimensions: slow.
- `clickhouse.queries_preempted`: Queries waiting due to priority (queries). Dimensions: preempted.
- `clickhouse.longest_running_query_time`: Longest running query time (seconds). Dimensions:
                                           longest_query_time.
- `clickhouse.queries_latency`: Queries latency (microseconds). Dimensions: queries_time.
- `clickhouse.select_queries_latency`: Select queries latency (microseconds). Dimensions:
                                       selects_time.
- `clickhouse.insert_queries_latency`: Insert queries latency (microseconds). Dimensions:
                                       inserts_time.
- `clickhouse.delayed_inserts_throttle_time`: Delayed inserts throttle time (milliseconds).
                                              Dimensions: delayed_inserts_throttle_time.
- `clickhouse.merges_latency`: Time spent for background merges (milliseconds). Dimensions:
                               merges_time.
- `clickhouse.uptime`: Uptime (seconds). Dimensions: uptime.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[clickhouse.slow_reads, clickhouse.queries_preempted, clickhouse.longest_running_query_time, clickhouse.queries_latency, clickhouse.select_queries_latency, clickhouse.insert_queries_latency] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="clickhouse.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="clickhouse.slow_reads"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
