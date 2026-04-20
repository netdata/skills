# Kubernetes Cluster State: Other Netdata Contexts signals

## Scope

Signals in the Other Netdata Contexts domain for Kubernetes Cluster State, as defined in the Netdata
operator playbook. Each signal includes a short description, the collection source, and a hint for
the MCP query pattern that surfaces it. Use this file during a triage pass to decide which signal to
pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

No structured signal list was extracted from the playbook for the Other Netdata Contexts domain.
Fall back to the MCP discovery pattern: run `list_metrics` filtered by the Kubernetes Cluster State
service and inspect anything with matching keywords.

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

These are the real Netdata chart contexts the native collector emits for Kubernetes Cluster State.
Use these names verbatim in `query_metrics` calls.

- `k8s_state.deployment_replicas`: Deployment Replicas (replicas). Dimensions: desired, current,
                                   ready.
- `k8s_state.deployment_age`: Deployment Age (seconds). Dimensions: age.
- `k8s_state.cronjob_jobs_failed_by_reason`: CronJob Jobs Failed by Reason (jobs). Dimensions:
                                             pod_failure_policy, backoff_limit_exceeded,
                                             deadline_exceeded.
- `k8s_state.cronjob_last_completed_time_ago`: CronJob Last Completed Time Ago (seconds).
                                               Dimensions: last_completed_ago.
- `k8s_state.cronjob_last_schedule_time_ago`: CronJob Last Schedule Time Ago (seconds). Dimensions:
                                              last_schedule_ago.
- `k8s_state.cronjob_age`: CronJob Age (seconds). Dimensions: age.
- `k8s_state.pod_phase`: Phase (state). Dimensions: running, failed, succeeded, pending.
- `k8s_state.pod_age`: Age (seconds). Dimensions: age.
- `k8s_state.pod_containers`: Containers (containers). Dimensions: containers, init_containers.
- `k8s_state.pod_containers_state`: Containers state (containers). Dimensions: running, waiting,
                                    terminated.
- `k8s_state.pod_init_containers_state`: Init containers state (containers). Dimensions: running,
                                         waiting, terminated.
- `k8s_state.pod_container_readiness_state`: Readiness state (state). Dimensions: ready.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[k8s_state.deployment_replicas, k8s_state.deployment_age, k8s_state.cronjob_jobs_failed_by_reason, k8s_state.cronjob_last_completed_time_ago, k8s_state.cronjob_last_schedule_time_ago, k8s_state.cronjob_age] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="k8s_state.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="k8s_state.deployment_replicas"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
