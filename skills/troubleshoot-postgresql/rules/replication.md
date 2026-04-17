# PostgreSQL: Replication signals

## Scope

Signals in the Replication domain for PostgreSQL, as defined in the Netdata operator playbook. Each
signal includes a short description, the collection source, and a hint for the MCP query pattern
that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Replication Lag [HIGH]

The difference between the primary's current WAL position and the standby's replayed position, in
bytes or time.

Collection source: On **primary**: `pg_stat_replication`; `sent_lsn`, `write_lsn`, `flush_lsn`,
`replay_lsn` (PG 10+); `write_lag`, `flush_lag`, `replay_lag` interval columns (PG 10+, primarily
useful for synchronous replication delay measurement). On **standby**: `pg_last_wal_receive_lsn()`,
`pg_last_wal_replay_ls...

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Replication Slot WAL Retention [HIGH]

WAL data retained because of replication slots. An inactive slot causes unbounded WAL growth.

Collection source: `pg_replication_slots`; `slot_name`, `slot_type`, `active`, `restart_lsn`,
`wal_status` (PG 13+), `safe_wal_size` (PG 13+).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Replication Connection Health [MEDIUM]

Whether expected standbys are connected and streaming, and the state of WAL receiver on standbys.

Collection source: On **primary**: `pg_stat_replication`; count of connected standbys, their
`state`, `sync_state`. On **standby**: `pg_stat_wal_receiver` (PG 9.6+); `status`,
`last_msg_receipt_time`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Standby Conflict Rate [MEDIUM]

The rate of queries canceled on hot standbys due to conflicts with WAL replay.

Collection source: `pg_stat_database_conflicts`; per-conflict-type counters (on **standby** only).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### WAL Archiver Status [MEDIUM]

Whether WAL archiving is functioning correctly.

Collection source: `pg_stat_archiver`; `archived_count`, `failed_count`, `last_archived_wal`,
`last_archived_time`, `last_failed_wal`, `last_failed_time`.

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

## MCP query examples for this domain

```text
# Pull every signal in this domain at once
query_metrics with contexts=[<signals from the list above>] and relative_window=-30m

# Ask the agent to rank anomalies that match this domain
find_anomalous_metrics filtered by any attribute unique to the PostgreSQL service (usually service.name or host.name)

# Look for correlated signals outside this domain
find_correlated_metrics around the incident window, limit 15
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
