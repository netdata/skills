# Kubernetes API Server: Overview signals

## Scope

Signals in the Overview domain for Kubernetes API Server, as defined in the Netdata operator
playbook. Each signal includes a short description, the collection source, and a hint for the MCP
query pattern that surfaces it. Use this file during a triage pass to decide which signal to pull
first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

No structured signal list was extracted from the playbook for the Overview domain. Fall back to the
MCP discovery pattern: run `list_metrics` filtered by the Kubernetes API Server service and inspect
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

These are the real Netdata chart contexts the native collector emits for Kubernetes API Server. Use
these names verbatim in `query_metrics` calls.

- `k8s_apiserver.requests_total`: API Server Request Rate (requests/s). Dimensions: requests.
- `k8s_apiserver.requests_dropped`: API Server Dropped Requests (requests/s). Dimensions: dropped.
- `k8s_apiserver.requests_by_verb`: API Server Requests By Verb (requests/s).
- `k8s_apiserver.requests_by_code`: API Server Requests By Status Code (requests/s).
- `k8s_apiserver.requests_by_resource`: API Server Requests By Resource (requests/s).
- `k8s_apiserver.request_latency`: API Server Request Latency (milliseconds). Dimensions: p50, p90,
                                   p99.
- `k8s_apiserver.response_size`: API Server Response Size (bytes). Dimensions: p50, p90, p99.
- `k8s_apiserver.inflight_requests`: API Server Inflight Requests (requests). Dimensions: mutating,
                                     read_only.
- `k8s_apiserver.longrunning_requests`: API Server Long-Running Requests (requests). Dimensions:
                                        longrunning.
- `k8s_apiserver.rest_client_requests_by_code`: REST Client Requests By Status Code (requests/s).
- `k8s_apiserver.rest_client_requests_by_method`: REST Client Requests By Method (requests/s).
- `k8s_apiserver.rest_client_latency`: REST Client Request Latency (milliseconds). Dimensions: p50,
                                       p90, p99.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[k8s_apiserver.requests_total, k8s_apiserver.requests_dropped, k8s_apiserver.requests_by_verb, k8s_apiserver.requests_by_code, k8s_apiserver.requests_by_resource, k8s_apiserver.request_latency] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="k8s_apiserver.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="k8s_apiserver.requests_total"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
