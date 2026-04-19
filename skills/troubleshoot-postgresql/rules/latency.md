# PostgreSQL: Latency signals

## Scope

Signals in the Latency domain for PostgreSQL, as defined in the Netdata operator playbook. Each
signal includes a short description, the collection source, and a hint for the MCP query pattern
that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Query Duration Distribution [HIGH]

The distribution of query execution times across all backends.

Collection source: `pg_stat_activity` for point-in-time snapshots; `pg_stat_statements` extension
for historical aggregates (mean, min, max, stddev, calls, total_exec_time).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Lock Wait Time [HIGH]

Time that queries spend waiting to acquire locks, and the depth of lock chains.

Collection source: `pg_stat_activity`; `wait_event_type = 'Lock'`; `pg_blocking_pids()` function (PG
9.6+) for identifying blockers; `pg_locks` for the full lock graph.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Checkpoint Duration and Frequency [HIGH]

How long each checkpoint takes and the ratio of timed vs. forced (requested) checkpoints.

Collection source: PG ≤ 16: `pg_stat_bgwriter`; `checkpoints_timed`, `checkpoints_req`,
`checkpoint_write_time`, `checkpoint_sync_time`, `buffers_checkpoint`, `buffers_backend`. PG 17+:
`pg_stat_checkpointer`; `num_timed`, `num_requested`, `write_time`, `sync_time`, `buffers_written`.
Server logs with `log_checkpoi...

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

These are the real Netdata chart contexts the native collector emits for PostgreSQL. Use these names
verbatim in `query_metrics` calls.

- `postgres.transactions_duration`: Observed transactions time (transactions/s).
- `postgres.queries_duration`: Observed active queries time (queries/s).
- `postgres.checkpoints_time`: Checkpoint time (milliseconds). Dimensions: write, sync.
- `postgres.uptime`: Uptime (seconds). Dimensions: uptime.
- `postgres.replication_app_wal_lag_time`: Standby application WAL lag time (seconds). Dimensions:
                                           write_lag, flush_lag, replay_lag.
- `postgres.db_locks_awaited_count`: Database locks awaited (locks). Dimensions: access_share,
                                     row_share, row_exclusive, share_update, share,
                                     share_row_exclusive.
- `postgres.table_autovacuum_since_time`: Table time since last auto VACUUM (seconds). Dimensions:
                                          time.
- `postgres.table_vacuum_since_time`: Table time since last manual VACUUM (seconds). Dimensions:
                                      time.
- `postgres.table_autoanalyze_since_time`: Table time since last auto ANALYZE (seconds). Dimensions:
                                           time.
- `postgres.table_analyze_since_time`: Table time since last manual ANALYZE (seconds). Dimensions:
                                       time.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[postgres.transactions_duration, postgres.queries_duration, postgres.checkpoints_time, postgres.uptime, postgres.replication_app_wal_lag_time, postgres.db_locks_awaited_count] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="postgres.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="postgres.transactions_duration"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
