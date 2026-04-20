# MySQL: Other Netdata Contexts signals

## Scope

Signals in the Other Netdata Contexts domain for MySQL, as defined in the Netdata operator playbook.
Each signal includes a short description, the collection source, and a hint for the MCP query
pattern that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

No structured signal list was extracted from the playbook for the Other Netdata Contexts domain.
Fall back to the MCP discovery pattern: run `list_metrics` filtered by the MySQL service and inspect
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

## Netdata contexts that surface Other Netdata Contexts

These are the real Netdata chart contexts the native collector emits for MySQL. Use these names
verbatim in `query_metrics` calls.

- `mysql.net`: Bandwidth (kilobits/s). Dimensions: in, out.
- `mysql.join_issues`: Table Select Join Issues (joins/s). Dimensions: full_join, full_range_join,
                       range, range_check, scan.
- `mysql.sort_issues`: Table Sort Issues (issues/s). Dimensions: merge_passes, range, scan.
- `mysql.innodb_io`: InnoDB I/O Bandwidth (KiB/s). Dimensions: read, write.
- `mysql.innodb_redo_log_activity`: InnoDB Redo Log Activity (B/s). Dimensions: redo_written,
                                    checkpointed.
- `mysql.innodb_redo_log_checkpoint_age`: InnoDB Redo Log Checkpoint Age (B). Dimensions: age.
- `mysql.innodb_os_log_io`: InnoDB OS Log Bandwidth (KiB/s). Dimensions: write.
- `mysql.innodb_deadlocks`: InnoDB Deadlocks (operations/s). Dimensions: deadlocks.
- `mysql.files`: Open Files (files). Dimensions: files.
- `mysql.opened_tables`: Opened Tables (tables/s). Dimensions: tables.
- `mysql.galera_queue`: Galera Queue (writesets). Dimensions: rx, tx.
- `mysql.galera_flow_control`: Flow Control (ms). Dimensions: paused.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[mysql.net, mysql.join_issues, mysql.sort_issues, mysql.innodb_io, mysql.innodb_redo_log_activity, mysql.innodb_redo_log_checkpoint_age] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="mysql.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="mysql.net"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
