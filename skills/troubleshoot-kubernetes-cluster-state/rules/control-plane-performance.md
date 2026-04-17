# Kubernetes Cluster State: Control Plane Performance signals

## Scope

Signals in the Control Plane Performance domain for Kubernetes Cluster State, as defined in the Netdata operator playbook. Each signal includes a short description, the collection source, and a hint for the MCP query pattern that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### API Server Request Latency (P99) [HIGH]

The 99th percentile latency for API server requests, indicating tail latency experienced by controllers, kubelets, and clients.

Collection source: - Metric: `apiserver_request_duration_seconds` (Histogram, STABLE) - Labels: `verb` (GET, LIST, POST, PUT, PATCH, DELETE), `resource`, `scope`

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### etcd WAL Fsync Latency [HIGH]

Time for etcd to fsync a Write-Ahead Log entry to disk. This happens on every write before etcd acknowledges it to the Raft quorum. This is the single most important etcd performance metric.

Collection source: - Metric: `etcd_disk_wal_fsync_duration_seconds` (Histogram)

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### etcd Backend Commit Latency [HIGH]

Time for etcd to commit an incremental snapshot of recent changes to the boltdb backend. This runs periodically (batched), not on every write.

Collection source: - Metric: `etcd_disk_backend_commit_duration_seconds` (Histogram)

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### API Server Inflight Requests [HIGH]

The number of requests currently being processed by the API server. When this hits the configured maximum (` -max-requests-inflight` for reads, ` -max-mutating-requests-inflight` for writes), new requests are rejected with HTTP 429.

Collection source: - Metric: `apiserver_current_inflight_requests` (Gauge, STABLE) - Labels: `request_kind` (mutating, readOnly)

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Admission Webhook Latency / Errors [HIGH]

Time spent in and errors from validating and mutating admission webhooks during API requests.

Collection source: - Metric: `apiserver_admission_webhook_admission_duration_seconds` (Histogram, STABLE) - Labels: `name` (webhook name), `type` (validating, mutating), `operation`, `rejected`

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Controller Workqueue Depth [HIGH]

The number of objects waiting to be processed by various controller reconciliation loops.

Collection source: - Metric: `workqueue_depth` (Gauge) - Labels: `name` (controller name: deployment, replicaset, endpoint, node, job, etc.)

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### API Priority and Fairness Rejections [HIGH]

Requests rejected by API Priority and Fairness (APF) flow control, which shapes API server traffic before it hits hard concurrency limits.

Collection source: - Metric: `apiserver_flowcontrol_rejected_requests_total` (Counter, BETA) - Labels: `flow_schema`, `priority_level`, `reason`

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
find_anomalous_metrics filtered by any attribute unique to the Kubernetes Cluster State service (usually service.name or host.name)

# Look for correlated signals outside this domain
find_correlated_metrics around the incident window, limit 15
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
