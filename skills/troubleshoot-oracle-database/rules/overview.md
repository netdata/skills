# Oracle Database: Overview signals

## Scope

Signals in the Overview domain for Oracle Database, as defined in the Netdata operator playbook.
Each signal includes a short description, the collection source, and a hint for the MCP query
pattern that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

No structured signal list was extracted from the playbook for the Overview domain. Fall back to the
MCP discovery pattern: run `list_metrics` filtered by the Oracle Database service and inspect
anything with matching keywords.

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

## Netdata contexts that surface Overview

These are the real Netdata chart contexts the native collector emits for Oracle Database. Use these
names verbatim in `query_metrics` calls.

- `oracledb.sessions`: Sessions (sessions). Dimensions: session.
- `oracledb.average_active_sessions`: Average Active Sessions (sessions). Dimensions: active.
- `oracledb.sessions_utilization`: Sessions Limit % (percent). Dimensions: session_limit.
- `oracledb.current_logons`: Current Logons (logons). Dimensions: logons.
- `oracledb.logons`: Logons (logons/s). Dimensions: logons.
- `oracledb.database_wait_time_ratio`: Database Wait Time Ratio (percent). Dimensions: db_wait_time.
- `oracledb.sql_service_response_time`: SQL Service Response Time (seconds). Dimensions:
                                        sql_resp_time.
- `oracledb.enqueue_timeouts`: Enqueue Timeouts (timeouts/s). Dimensions: enqueue.
- `oracledb.disk_io`: Disk IO (bytes/s). Dimensions: read, written.
- `oracledb.disk_iops`: Disk IOPS (operations/s). Dimensions: read, write.
- `oracledb.sorts`: Sorts (sorts/s). Dimensions: memory, disk.
- `oracledb.table_scans`: Table Scans (scans/s). Dimensions: short_table, long_table.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[oracledb.sessions, oracledb.average_active_sessions, oracledb.sessions_utilization, oracledb.current_logons, oracledb.logons, oracledb.database_wait_time_ratio] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="oracledb.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="oracledb.sessions"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
