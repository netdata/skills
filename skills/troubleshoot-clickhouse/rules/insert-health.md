# ClickHouse: Insert Health signals

## Scope

Signals in the Insert Health domain for ClickHouse, as defined in the Netdata operator playbook.
Each signal includes a short description, the collection source, and a hint for the MCP query
pattern that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Insert Delays and Rejections [HIGH]

Whether ClickHouse is artificially slowing down (delaying) or outright rejecting INSERT operations
due to excessive part counts.

Collection source: - System events: `system.events` then `DelayedInserts`, `RejectedInserts` - These
are cumulative counters since server start

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

## Netdata contexts that surface Insert Health

These are the real Netdata chart contexts the native collector emits for ClickHouse. Use these names
verbatim in `query_metrics` calls.

- `clickhouse.insert_queries`: Insert queries (inserts/s). Dimensions: successful, failed.
- `clickhouse.insert_queries_latency`: Insert queries latency (microseconds). Dimensions:
                                       inserts_time.
- `clickhouse.inserted_rows`: Inserted rows (rows/s). Dimensions: inserted.
- `clickhouse.inserted_bytes`: Inserted data (bytes/s). Dimensions: inserted.
- `clickhouse.rejected_inserts`: Rejected inserts (inserts/s). Dimensions: rejected.
- `clickhouse.delayed_inserts`: Delayed inserts (inserts/s). Dimensions: delayed.
- `clickhouse.delayed_inserts_throttle_time`: Delayed inserts throttle time (milliseconds).
                                              Dimensions: delayed_inserts_throttle_time.
- `clickhouse.merge_tree_data_writer_inserted_rows`: Rows INSERTed to MergeTree tables (rows/s).
                                                     Dimensions: inserted.
- `clickhouse.merge_tree_data_writer_uncompressed_bytes`: Data INSERTed to MergeTree tables
                                                          (bytes/s). Dimensions: inserted.
- `clickhouse.merge_tree_data_writer_compressed_bytes`: Data written to disk for data INSERTed to
                                                        MergeTree tables (bytes/s). Dimensions:
                                                        written.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[clickhouse.insert_queries, clickhouse.insert_queries_latency, clickhouse.inserted_rows, clickhouse.inserted_bytes, clickhouse.rejected_inserts, clickhouse.delayed_inserts] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="clickhouse.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="clickhouse.insert_queries"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
