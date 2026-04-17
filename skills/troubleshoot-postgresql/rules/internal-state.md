# PostgreSQL: Internal State signals

## Scope

Signals in the Internal State domain for PostgreSQL, as defined in the Netdata operator playbook. Each signal includes a short description, the collection source, and a hint for the MCP query pattern that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Transaction ID Wraparound Proximity [HIGH]

The age of the oldest unfrozen transaction ID in the database. PostgreSQL uses a 32-bit XID with circular arithmetic; half the 2^32 space (2,147,483,648 XIDs) is "in the past." If the database exhausts this window, it refuses all writes.

Collection source: `pg_database`; `age(datfrozenxid)` for per-database; `pg_class`; `age(relfrozenxid)` for per-table. TOAST tables have their own relfrozenxid.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Multixact ID Wraparound Proximity [MEDIUM]

The age of the oldest multixact ID in the database. Multixacts are used for row-level locking when multiple transactions hold shared locks on the same row. Like XIDs, they have a wraparound risk.

Collection source: `pg_database`; `age(datminmxid)`; `pg_class`; `mxid_age(relminmxid)`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Dead Tuple Count / Table Bloat [HIGH]

Dead tuples accumulating in tables, waiting for vacuum to reclaim them.

Collection source: `pg_stat_user_tables`; `n_dead_tup`, `n_live_tup`, `last_autovacuum`, `autovacuum_count`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Autovacuum Worker Activity [HIGH]

The current state of autovacuum: worker count, tables being vacuumed, progress, and whether anti-wraparound vacuum is active.

Collection source: `pg_stat_activity`; filter for autovacuum workers; `pg_stat_progress_vacuum` (PG 9.6+).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Buffer Cache Hit Ratio [HIGH]

Percentage of data block requests served from shared buffers versus read from disk.

Collection source: `pg_stat_database`; `blks_hit` and `blks_read` (cumulative counters).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Temp File Usage [MEDIUM]

Volume and count of temporary files created by queries exceeding work_mem.

Collection source: `pg_stat_database`; `temp_files` and `temp_bytes` (cumulative counters; available in PG 9.2+).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Deadlock Rate [HIGH]

Number of deadlocks detected and resolved by PostgreSQL.

Collection source: `pg_stat_database`; `deadlocks` counter (cumulative).

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
find_anomalous_metrics filtered by any attribute unique to the PostgreSQL service (usually service.name or host.name)

# Look for correlated signals outside this domain
find_correlated_metrics around the incident window, limit 15
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
