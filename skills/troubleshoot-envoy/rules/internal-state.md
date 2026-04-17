# Envoy: Internal State signals

## Scope

Signals in the Internal State domain for Envoy, as defined in the Netdata operator playbook. Each signal includes a short description, the collection source, and a hint for the MCP query pattern that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Control Plane Connection State [HIGH]

Whether Envoy is currently connected to its xDS control plane.

Collection source: Stat: `control_plane.connected_state` (gauge: 1=connected, 0=disconnected).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Cluster and Listener Warming State [MEDIUM]

The number of clusters and listeners in "warming" state; received via xDS but not yet active.

Collection source: Stats: `cluster_manager.warming_clusters` (gauge), `listener_manager.total_listeners_warming` (gauge).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Outlier Detection Ejections [MEDIUM]

The number of upstream hosts currently ejected from load balancing by outlier detection, and the rate of ejection events.

Collection source: Stats: `cluster.<name>.outlier_detection.ejections_active` (gauge; currently ejected hosts), `cluster.<name>.outlier_detection.ejections_enforced_total` (counter; total enforced ejections), plus detailed per-type counters: `ejections_enforced_consecutive_5xx`, `ejections_enforced_success_rate`, `...

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Worker Thread Utilization (Watchdog) [HIGH]

How busy each worker thread's event loop is; whether workers are blocked or saturated.

Collection source: Stats: `server.watchdog_miss` (counter; incremented when main thread's watchdog detects a worker hasn't responded in time), `server.watchdog_mega_miss` (counter; longer blocking threshold). If `enable_dispatcher_stats` is enabled: `listener.worker_<id>.dispatcher.loop_duration_us` and `listener.w...

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Retry Amplification [MEDIUM]

The rate of upstream request retries and the relationship between retry volume and total request volume.

Collection source: Stats: `cluster.<name>.upstream_rq_retry` (counter), `cluster.<name>.upstream_rq_retry_success` (counter), `cluster.<name>.upstream_rq_retry_overflow` (counter), `cluster.<name>.upstream_rq_retry_limit_exceeded` (counter).

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
