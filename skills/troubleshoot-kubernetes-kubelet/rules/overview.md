# Kubernetes Kubelet: Overview signals

## Scope

Signals in the Overview domain for Kubernetes Kubelet, as defined in the Netdata operator playbook.
Each signal includes a short description, the collection source, and a hint for the MCP query
pattern that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

No structured signal list was extracted from the playbook for the Overview domain. Fall back to the
MCP discovery pattern: run `list_metrics` filtered by the Kubernetes Kubelet service and inspect
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

## Netdata contexts that surface Overview

These are the real Netdata chart contexts the native collector emits for Kubernetes Kubelet. Use
these names verbatim in `query_metrics` calls.

- `k8s_kubelet.apiserver_audit_requests_rejected`: API Server Audit Requests (requests/s).
                                                   Dimensions: rejected.
- `k8s_kubelet.apiserver_storage_data_key_generation_failures`: API Server Failed Data Encryption
                                                                Key(DEK) Generation Operations
                                                                (events/s). Dimensions: failures.
- `k8s_kubelet.apiserver_storage_data_key_generation_latencies`: API Server Latencies Of Data
                                                                 Encryption Key(DEK) Generation
                                                                 Operations (observes/s).
                                                                 Dimensions: 5_µs, 10_µs, 20_µs,
                                                                 40_µs, 80_µs, 160_µs.
- `k8s_kubelet.apiserver_storage_data_key_generation_latencies_percent`: API Server Latencies Of
                                                                         Data Encryption Key(DEK)
                                                                         Generation Operations
                                                                         Percentage (percentage).
                                                                         Dimensions: 5_µs, 10_µs,
                                                                         20_µs, 40_µs, 80_µs,
                                                                         160_µs.
- `k8s_kubelet.apiserver_storage_envelope_transformation_cache_misses`: API Server Storage Envelope
                                                                        Transformation Cache Misses
                                                                        (events/s). Dimensions:
                                                                        cache misses.
- `k8s_kubelet.kubelet_containers_running`: Number Of Containers Currently Running
                                            (running_containers). Dimensions: total.
- `k8s_kubelet.kubelet_pods_running`: Number Of Pods Currently Running (running_pods). Dimensions:
                                      total.
- `k8s_kubelet.kubelet_pods_log_filesystem_used_bytes`: Bytes Used By The Pod Logs On The Filesystem
                                                        (B).
- `k8s_kubelet.kubelet_runtime_operations`: Runtime Operations By Type (operations/s).
- `k8s_kubelet.kubelet_runtime_operations_errors`: Runtime Operations Errors By Type (errors/s).
- `k8s_kubelet.kubelet_docker_operations`: Docker Operations By Type (operations/s).
- `k8s_kubelet.kubelet_docker_operations_errors`: Docker Operations Errors By Type (errors/s).

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[k8s_kubelet.apiserver_audit_requests_rejected, k8s_kubelet.apiserver_storage_data_key_generation_failures, k8s_kubelet.apiserver_storage_data_key_generation_latencies, k8s_kubelet.apiserver_storage_data_key_generation_latencies_percent, k8s_kubelet.apiserver_storage_envelope_transformation_cache_misses, k8s_kubelet.kubelet_containers_running] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="k8s_kubelet.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="k8s_kubelet.apiserver_audit_requests_rejected"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
