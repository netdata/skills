# MySQL: Saturation signals

## Scope

Signals in the Saturation domain for MySQL, as defined in the Netdata operator playbook. Each signal
includes a short description, the collection source, and a hint for the MCP query pattern that
surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### InnoDB Buffer Pool Hit Ratio [HIGH]

The percentage of data page reads served from memory vs disk.

Collection source: Derived from: `1 - (Innodb_buffer_pool_reads / Innodb_buffer_pool_read_requests)`
Both are cumulative counters in `SHOW GLOBAL STATUS`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Buffer Pool Memory Pressure (Wait Free) [HIGH]

Count of times a query had to wait because no clean buffer pool pages were available.

Collection source: `SHOW GLOBAL STATUS LIKE 'Innodb_buffer_pool_wait_free';`; cumulative counter.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### InnoDB Redo Log Checkpoint Age [HIGH]

The difference between the current log sequence number (LSN) and the last checkpoint LSN. Represents
how much redo log space is in use.

Collection source: MySQL 8.0.30+: `SHOW GLOBAL STATUS`; compute as `Innodb_redo_log_current_lsn -
Innodb_redo_log_checkpoint_lsn`. Pre-8.0.30: `INFORMATION_SCHEMA.INNODB_METRICS`; metric
`log_lsn_checkpoint_age` (disabled by default, enable with `SET GLOBAL innodb_monitor_enable =
'log_lsn_checkpoint_age'`). All ve...

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### InnoDB Log Buffer Waits [HIGH]

Count of times the log buffer was too small, requiring a flush before continuing.

Collection source: `SHOW GLOBAL STATUS LIKE 'Innodb_log_waits';`; cumulative counter. Available in
MySQL 5.7, 8.0, and 8.4. Still relevant in MySQL 8.0.30+ (log buffer concept unchanged).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Durability Path Latency (Fsync Pressure) [HIGH]

The rate and latency of redo log and binary log fsync operations; the critical path for durable
commits.

Collection source: `SHOW GLOBAL STATUS LIKE 'Innodb_os_log_fsyncs';`; cumulative counter of redo log
fsyncs. `SHOW GLOBAL STATUS LIKE 'Innodb_os_log_pending_fsyncs';`; instantaneous gauge of pending
fsyncs. `SHOW GLOBAL STATUS LIKE 'Innodb_os_log_pending_writes';`; instantaneous gauge of pending
log writes.

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
find_anomalous_metrics filtered by any attribute unique to the MySQL service (usually service.name or host.name)

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
