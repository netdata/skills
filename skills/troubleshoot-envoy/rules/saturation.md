# Envoy: Saturation signals

## Scope

Signals in the Saturation domain for Envoy, as defined in the Netdata operator playbook. Each signal includes a short description, the collection source, and a hint for the MCP query pattern that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Upstream Pending Request Queue [HIGH]

The number of requests queued waiting for an available upstream connection, and the overflow count when the queue is full.

Collection source: Stats: `cluster.<name>.upstream_rq_pending_active` (gauge), `cluster.<name>.upstream_rq_pending_overflow` (counter).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Circuit Breaker State [HIGH]

Whether any circuit breaker (connections, pending requests, requests, retries) has tripped for a cluster.

Collection source: Stats: `cluster.<name>.circuit_breakers.<priority>.cx_open` (gauge, 0 or 1), `rq_pending_open` (gauge), `rq_open` (gauge), `rq_retry_open` (gauge). Priority levels: `default`, `high`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Upstream Active Connections [MEDIUM]

The number of currently active connections in the upstream connection pool for each cluster.

Collection source: Stat: `cluster.<name>.upstream_cx_active` (gauge).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Server Memory Usage [MEDIUM]

Envoy's memory consumption: allocated memory, heap size, and physical memory.

Collection source: Stats: `server.memory_allocated` (gauge, bytes), `server.memory_heap_size` (gauge, bytes), `server.memory_physical_size` (gauge, bytes).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Overload Manager Actions [HIGH]

Whether Envoy's overload manager has been triggered and what protective actions it is taking. The overload manager is Envoy's last line of defense before OOM.

Collection source: Stats: `server.overload_manager.envoy.overload_actions.<action_name>.active` (gauge, 1 if active). Common actions: `stop_accepting_requests`, `stop_accepting_connections`, `shrink_heap`, `reduce_timeouts`, `disable_http_keepalive`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### File Descriptor Utilization [HIGH]

The number of open file descriptors by the Envoy process relative to the OS/container limit. FD exhaustion is a hard cliff; when it hits, Envoy cannot accept new connections or open new upstream connections.

Collection source: Linux proc filesystem: `/proc/<envoy_pid>/fd/` (count entries) and `/proc/<envoy_pid>/limits` (Max open files). Stat proxy: `server.total_connections` (gauge); each proxied connection ≈ 2 FDs (downstream + upstream).

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
find_anomalous_metrics filtered by any attribute unique to the Envoy service (usually service.name or host.name)

# Look for correlated signals outside this domain
find_correlated_metrics around the incident window, limit 15
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
