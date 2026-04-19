# MySQL: Resource Utilization signals

## Scope

Signals in the Resource Utilization domain for MySQL, as defined in the Netdata operator playbook.
Each signal includes a short description, the collection source, and a hint for the MCP query
pattern that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Thread Creation Rate [HIGH]

Rate at which MySQL creates new threads for connections (instead of reusing cached threads).

Collection source: `SHOW GLOBAL STATUS LIKE 'Threads_created';`; cumulative counter. `SHOW GLOBAL
STATUS LIKE 'Threads_cached';`; current cached threads.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Temporary Table Disk Usage [HIGH]

The proportion of temporary tables that spill from memory to disk.

Collection source: `SHOW GLOBAL STATUS LIKE 'Created_tmp_disk_tables';`; cumulative counter. `SHOW
GLOBAL STATUS LIKE 'Created_tmp_tables';`; cumulative counter.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Query Quality Indicators (Full Scans / Join Efficiency) [MEDIUM]

Handler and join counters that indicate query plan quality; full table scans, joins without indexes,
and filesort overhead.

Collection source: `SHOW GLOBAL STATUS LIKE 'Handler_read_rnd_next';`; primary full table scan
indicator (cumulative counter). `SHOW GLOBAL STATUS LIKE 'Handler_read_rnd';`; random positional
reads from filesort (cumulative counter). `SHOW GLOBAL STATUS LIKE 'Select_full_join';`; joins
without index (cumulative cou...

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

## Netdata contexts that surface Resource Utilization

These are the real Netdata chart contexts the native collector emits for MySQL. Use these names
verbatim in `query_metrics` calls.

- `mysql.table_open_cache_overflows`: Table open cache overflows (overflows/s). Dimensions:
                                      open_cache.
- `mysql.tmp`: Tmp Operations (events/s). Dimensions: disk_tables, files, tables.
- `mysql.threads`: Threads (threads). Dimensions: connected, cached, running.
- `mysql.thread_cache_misses`: Threads Cache Misses (misses). Dimensions: misses.
- `mysql.innodb_io_ops`: InnoDB I/O Operations (operations/s). Dimensions: reads, writes, fsyncs.
- `mysql.innodb_io_pending_ops`: InnoDB Pending I/O Operations (operations). Dimensions: reads,
                                 writes, fsyncs.
- `mysql.innodb_log`: InnoDB Log Operations (operations/s). Dimensions: waits, write_requests,
                      writes.
- `mysql.innodb_rows`: InnoDB Row Operations (operations/s). Dimensions: inserted, read, updated,
                       deleted.
- `mysql.innodb_buffer_pool_pages`: InnoDB Buffer Pool Pages (pages). Dimensions: data, dirty, free,
                                    misc, total.
- `mysql.innodb_buffer_pool_pages_flushed`: InnoDB Buffer Pool Flush Pages Requests (requests/s).
                                            Dimensions: flush_pages.
- `mysql.innodb_buffer_pool_bytes`: InnoDB Buffer Pool Bytes (MiB). Dimensions: data, dirty.
- `mysql.innodb_buffer_pool_read_ahead`: InnoDB Buffer Pool Read Pages (pages/s). Dimensions: all,
                                         evicted.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[mysql.table_open_cache_overflows, mysql.tmp, mysql.threads, mysql.thread_cache_misses, mysql.innodb_io_ops, mysql.innodb_io_pending_ops] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="mysql.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="mysql.table_open_cache_overflows"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
