# ClickHouse: Internal State; Parts And Merges signals

## Scope

Signals in the Internal State; Parts And Merges domain for ClickHouse, as defined in the Netdata
operator playbook. Each signal includes a short description, the collection source, and a hint for
the MCP query pattern that surfaces it. Use this file during a triage pass to decide which signal to
pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Active Part Count Per Table [HIGH]

The number of active (non-obsolete) data parts currently existing for each MergeTree table. This is
the single most important health indicator for ClickHouse write performance and the primary
predictor of "too many parts" failures.

Collection source: - System table: `system.parts` (column `active`) - System async metric:
`system.asynchronous_metrics` then `MaxPartCountForPartition` (maximum part count across all
partitions of all MergeTree tables)

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Merge Activity and Progress [HIGH]

Information about currently running merge operations; whether merges are actually happening, how
much work they're doing, and whether they're making progress.

Collection source: - System table: `system.merges` - Key columns: `elapsed`, `progress`,
`num_parts`, `is_mutation`, `memory_usage`

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Mutation Status and Queue [HIGH]

Information about ALTER UPDATE/DELETE mutations; long-running background operations that rewrite
parts and can block merges.

Collection source: - System table: `system.mutations` - Key columns: `is_done`, `parts_to_do`,
`latest_fail_time`, `latest_fail_reason`

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Replication Queue Depth [HIGH]

The number of pending replication log entries that need to be applied to bring a replica up to date.
Shows replication health at the operational level.

Collection source: - System table: `system.replicas` then `queue_size`, `inserts_in_queue`,
`merges_in_queue`, `log_max_index - log_pointer` - System table: `system.replication_queue` for
detailed per-entry view

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Replication Lag (Time-Based) [HIGH]

Wall-clock seconds since the oldest unprocessed insert in the replication queue. The primary
time-based metric for data freshness on a replica.

Collection source: - System table: `system.replicas` then `absolute_delay` column

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

## Netdata contexts that surface Internal State; Parts And Merges

These are the real Netdata chart contexts the native collector emits for ClickHouse. Use these names
verbatim in `query_metrics` calls.

- `clickhouse.replicated_parts_current_activity`: Replicated parts current activity (parts).
                                                  Dimensions: fetch, send, check.
- `clickhouse.replicated_readonly_tables`: Replicated tables in readonly state (tables). Dimensions:
                                           read_only.
- `clickhouse.selected_parts`: Selected parts (parts/s). Dimensions: selected.
- `clickhouse.merges`: Merge operations (ops/s). Dimensions: merge.
- `clickhouse.merges_latency`: Time spent for background merges (milliseconds). Dimensions:
                               merges_time.
- `clickhouse.merged_uncompressed_bytes`: Uncompressed data read for background merges (bytes/s).
                                          Dimensions: merged_uncompressed.
- `clickhouse.max_part_count_for_partition`: Max part count for partition (parts). Dimensions:
                                             max_parts_partition.
- `clickhouse.parts_count`: Parts (parts). Dimensions: temporary, pre_active, active, deleting,
                            delete_on_destroy, outdated.
- `clickhouse.database_table_parts`: Table parts (parts). Dimensions: parts.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[clickhouse.replicated_parts_current_activity, clickhouse.replicated_readonly_tables, clickhouse.selected_parts, clickhouse.merges, clickhouse.merges_latency, clickhouse.merged_uncompressed_bytes] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="clickhouse.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="clickhouse.replicated_parts_current_activity"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
