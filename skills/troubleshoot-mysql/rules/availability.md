# MySQL: Availability signals

## Scope

Signals in the Availability domain for MySQL, as defined in the Netdata operator playbook. Each
signal includes a short description, the collection source, and a hint for the MCP query pattern
that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### MySQL Server Availability [HIGH]

Whether the MySQL server is up and responsive to connections and queries.

Collection source: A TCP connect to the MySQL port (default 3306) + `SELECT 1` or equivalent
liveness query. Also: `SHOW GLOBAL STATUS LIKE 'Uptime';`; seconds since last restart.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Connection Utilization [HIGH]

The ratio of currently open connections to the configured maximum. Indicates how close the instance
is to refusing new connections.

Collection source: `SHOW GLOBAL STATUS LIKE 'Threads_connected';` `SHOW GLOBAL VARIABLES LIKE
'max_connections';` Also: `Max_used_connections` for historical peak.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Replication Thread State [HIGH]

Whether the I/O thread and SQL/applier thread(s) are running on a replica.

Collection source: ```sql SHOW REPLICA STATUS\G - Replica_IO_Running: Yes/No/Connecting (8.0.22+) -
Replica_SQL_Running: Yes/No (8.0.22+) - Legacy: SHOW SLAVE STATUS with Slave_IO_Running /
Slave_SQL_Running (5.7, deprecated in 8.0) ```

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

## Netdata contexts that surface Availability

These are the real Netdata chart contexts the native collector emits for MySQL. Use these names
verbatim in `query_metrics` calls.

- `mysql.queries_type`: Queries By Type (queries/s). Dimensions: select, delete, update, insert,
                        replace.
- `mysql.handlers`: Handlers (handlers/s). Dimensions: commit, delete, prepare, read_first,
                    read_key, read_next.
- `mysql.connections`: Connections (connections/s). Dimensions: all, aborted.
- `mysql.connections_active`: Active Connections (connections). Dimensions: active, limit,
                              max_active.
- `mysql.threads`: Threads (threads). Dimensions: connected, cached, running.
- `mysql.innodb_redo_log_occupancy`: InnoDB Redo Log Occupancy (percentage). Dimensions: occupancy.
- `mysql.innodb_rows`: InnoDB Row Operations (operations/s). Dimensions: inserted, read, updated,
                       deleted.
- `mysql.connection_errors`: Connection Errors (errors/s). Dimensions: accept, internal, max,
                             peer_addr, select, tcpwrap.
- `mysql.galera_cluster_status`: Cluster Component Status (status). Dimensions: primary,
                                 non_primary, disconnected.
- `mysql.galera_connected`: Cluster Connection Status (boolean). Dimensions: connected.
- `mysql.galera_ready`: Accept Queries Readiness Status (boolean). Dimensions: ready.
- `mysql.slave_status`: I/O / SQL Thread Running State (boolean). Dimensions: sql_running,
                        io_running.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[mysql.queries_type, mysql.handlers, mysql.connections, mysql.connections_active, mysql.threads, mysql.innodb_redo_log_occupancy] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="mysql.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="mysql.queries_type"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
