# Envoy: Availability signals

## Scope

Signals in the Availability domain for Envoy, as defined in the Netdata operator playbook. Each
signal includes a short description, the collection source, and a hint for the MCP query pattern
that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Server State [HIGH]

Whether the Envoy process is running and in what lifecycle state: LIVE, DRAINING, PRE_INITIALIZING,
or INITIALIZING.

Collection source: Admin endpoint: `GET /ready` (returns 200 for LIVE, 503 otherwise). Stat:
`server.state` (gauge: 0=LIVE, 1=DRAINING, 2=PRE_INITIALIZING, 3=INITIALIZING).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Upstream Host Health [HIGH]

The number of upstream hosts in each health state (healthy, degraded, excluded) within each cluster,
as determined by active health checks and outlier detection.

Collection source: Stats: `cluster.<name>.membership_healthy` (gauge),
`cluster.<name>.membership_degraded` (gauge), `cluster.<name>.membership_excluded` (gauge),
`cluster.<name>.membership_total` (gauge). Admin: `GET /clusters?format=json` provides per-host
detail.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Listener Active Connections [HIGH]

The count of currently active downstream (client-facing) connections per listener.

Collection source: Stat: `listener.<address>.downstream_cx_active` (gauge).

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

These are the real Netdata chart contexts the native collector emits for Envoy. Use these names
verbatim in `query_metrics` calls.

- `envoy.server_connections_count`: Server current connections (connections). Dimensions:
                                    connections.
- `envoy.server_parent_connections_count`: Server current parent connections (connections).
                                           Dimensions: connections.
- `envoy.server_uptime`: Server uptime (seconds). Dimensions: uptime.
- `envoy.cluster_manager_cluster_updates_rate`: Cluster manager updates (updates/s). Dimensions:
                                                cluster.
- `envoy.cluster_manager_cluster_updated_via_merge_rate`: Cluster manager updates applied as merged
                                                          updates (updates/s). Dimensions:
                                                          via_merge.
- `envoy.cluster_manager_update_merge_cancelled_rate`: Cluster manager cancelled merged updates
                                                       (updates/s). Dimensions: merge_cancelled.
- `envoy.cluster_manager_update_out_of_merge_window_rate`: Cluster manager out of a merge window
                                                           updates (updates/s). Dimensions:
                                                           out_of_merge_window.
- `envoy.cluster_membership_endpoints_count`: Cluster membership current endpoints (endpoints).
                                              Dimensions: healthy, degraded, excluded.
- `envoy.cluster_membership_updates_rate`: Cluster membership updates (updates/s). Dimensions:
                                           success, failure, empty, no_rebuild.
- `envoy.cluster_upstream_cx_active_count`: Cluster upstream current active connections
                                            (connections). Dimensions: active.
- `envoy.cluster_upstream_cx_rate`: Cluster upstream connections (connections/s). Dimensions:
                                    created.
- `envoy.cluster_upstream_cx_http_rate`: Cluster upstream connections by HTTP version
                                         (connections/s). Dimensions: http1, http2, http3.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[envoy.server_connections_count, envoy.server_parent_connections_count, envoy.server_uptime, envoy.cluster_manager_cluster_updates_rate, envoy.cluster_manager_cluster_updated_via_merge_rate, envoy.cluster_manager_update_merge_cancelled_rate] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="envoy.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="envoy.server_connections_count"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
