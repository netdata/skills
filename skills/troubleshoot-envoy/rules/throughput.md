# Envoy: Throughput signals

## Scope

Signals in the Throughput domain for Envoy, as defined in the Netdata operator playbook. Each signal
includes a short description, the collection source, and a hint for the MCP query pattern that
surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Upstream Request Rate [HIGH]

The rate of requests sent to upstream clusters.

Collection source: Stat: `cluster.<name>.upstream_rq_total` (counter).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Downstream Request Rate [MEDIUM]

The rate of HTTP requests received from downstream clients.

Collection source: Stat: `http.<stat_prefix>.downstream_rq_total` (counter). The `stat_prefix` comes
from the HTTP connection manager configuration.

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

## Netdata contexts that surface Throughput

These are the real Netdata chart contexts the native collector emits for Envoy. Use these names
verbatim in `query_metrics` calls.

- `envoy.cluster_manager_cluster_changes_rate`: Cluster manager cluster changes (clusters/s).
                                                Dimensions: added, modified, removed.
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
- `envoy.cluster_membership_changes_rate`: Cluster membership changes (changes/s). Dimensions:
                                           membership.
- `envoy.cluster_membership_updates_rate`: Cluster membership updates (updates/s). Dimensions:
                                           success, failure, empty, no_rebuild.
- `envoy.cluster_upstream_cx_rate`: Cluster upstream connections (connections/s). Dimensions:
                                    created.
- `envoy.cluster_upstream_cx_http_rate`: Cluster upstream connections by HTTP version
                                         (connections/s). Dimensions: http1, http2, http3.
- `envoy.cluster_upstream_cx_destroy_rate`: Cluster upstream destroyed connections (connections/s).
                                            Dimensions: local, remote.
- `envoy.cluster_upstream_cx_connect_fail_rate`: Cluster upstream failed connections
                                                 (connections/s). Dimensions: failed.
- `envoy.cluster_upstream_cx_connect_timeout_rate`: Cluster upstream timed out connections
                                                    (connections/s). Dimensions: timeout.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[envoy.cluster_manager_cluster_changes_rate, envoy.cluster_manager_cluster_updates_rate, envoy.cluster_manager_cluster_updated_via_merge_rate, envoy.cluster_manager_update_merge_cancelled_rate, envoy.cluster_manager_update_out_of_merge_window_rate, envoy.cluster_membership_changes_rate] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="envoy.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="envoy.cluster_manager_cluster_changes_rate"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
