# Kubernetes Cluster State: Workload Health signals

## Scope

Signals in the Workload Health domain for Kubernetes Cluster State, as defined in the Netdata
operator playbook. Each signal includes a short description, the collection source, and a hint for
the MCP query pattern that surfaces it. Use this file during a triage pass to decide which signal to
pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Deployment Available Replicas [HIGH]

Whether Deployments have their desired number of available replicas. The Deployment controller
defines "available" as replicas that have been ready for at least `minReadySeconds` (default 0);
this is a controller-level status field, not simply "ready + running."

Collection source: - Metric: `kube_deployment_status_replicas_available` vs
`kube_deployment_spec_replicas` (STABLE) - Metric: `kube_deployment_status_condition` (STABLE);
deployment conditions including `Available` and `Progressing` - API: Deployment status

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Deployment Rollout Progress [HIGH]

Whether a Deployment rollout is making progress or has stalled (ProgressDeadlineExceeded).

Collection source: - Metric:
`kube_deployment_status_condition{condition="Progressing",status="false"}` (STABLE); indicates
ProgressDeadlineExceeded - API: Deployment conditions

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### StatefulSet Ready Replicas [HIGH]

Whether StatefulSets have their desired number of ready replicas.

Collection source: - Metric: `kube_statefulset_status_replicas_ready` vs `kube_statefulset_replicas`
(STABLE)

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### DaemonSet Desired vs Ready [HIGH]

Whether DaemonSets have pods running on all targeted nodes.

Collection source: - Metric: `kube_daemonset_status_number_ready` vs
`kube_daemonset_status_desired_number_scheduled` (STABLE)

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Job / CronJob Health [HIGH]

Whether Jobs complete successfully and CronJobs run on schedule.

Collection source: - Metric: `kube_job_status_failed` (STABLE); count of failed pods in a job -
Metric: `kube_job_status_succeeded` (STABLE); count of succeeded pods - Metric: `kube_job_complete`
(STABLE); job completion status - Metric: `kube_cronjob_next_schedule_time` (STABLE); next expected
run - Metric: `kube_...

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Service with Zero Endpoints [HIGH]

Services that have no ready endpoints; all backend pods are either down, not ready, or the selector
doesn't match any pods.

Collection source: - Metric: `kube_endpoint_address{ready="true"}` (STABLE); count by service - API:
`kubectl get endpoints`

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### ResourceQuota Utilization [HIGH]

How close namespaces are to their configured resource quotas, which can silently block new pod
creation and deployments.

Collection source: - Metric: `kube_resourcequota` (STABLE); labels: `resource`, `type` (hard, used),
`namespace`

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

## Netdata contexts that surface Workload Health

No Netdata-native contexts were classified into the Workload Health domain for Kubernetes Cluster
State. Use discovery-style MCP calls below, or consult the full context list in SKILL.md.

## MCP query examples for this domain

```text
# Discover contexts for this service
list_metrics with q="kubernetes-cluster-state"

# Rank anomalies on the host running this service
find_anomalous_metrics with node=<host>
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
