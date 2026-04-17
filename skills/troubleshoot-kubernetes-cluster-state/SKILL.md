---
name: troubleshoot-kubernetes-cluster-state
description: "Use when diagnosing issues with Kubernetes Cluster State: Kubernetes Cluster State operational issues. Queries Netdata via MCP for api server health, etcd leader existence, api server request latency (p99), etcd wal fsync latency, etcd leader changes, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - kubernetes-cluster-state
---

# Troubleshoot Kubernetes Cluster State

## When to use this skill

- Any time the user reports a Kubernetes Cluster State service behaving outside its expected envelope (elevated errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a Kubernetes Cluster State instance and wants a structured triage path.

## Key facts

- This skill wraps the Netdata operator playbook for Kubernetes Cluster State. It does not replace the playbook; it routes a coding agent through MCP queries against the same signals the playbook relies on.
- Kubernetes is a distributed state machine. Every object; Pod, Deployment, Service, Node, PersistentVolumeClaim; has a **desired state** (what you declared in YAML) and a **current state** (what actually exists). The entire control plane exists to reconcile these two states continuously. When monitoring cluster state, you are monitoring the health and velocity of this reconciliation loop.
- The playbook decomposes Kubernetes Cluster State health into 13 signal domains: Control Plane Availability, Control Plane Performance, etcd Health, Node Health, Kubelet Health, Pod Lifecycle. Each domain maps to one rule file in this skill.
- Netdata observes the signals listed in the rule files via its native collectors, plus any OpenTelemetry-shipped metrics that your Kubernetes Cluster State instrumentation adds. Both paths end at the same MCP query surface.

## Step-by-step

1. Confirm the Kubernetes Cluster State service is up. Query Netdata via MCP with `list_nodes` and filter by the host running the target. A missing node means the symptom is at the network or orchestrator layer, not inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window; anomalies frame which rule file to read first.
3. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`, `system.disk.io_time`). Many service-level failures have a host-resource precursor.
4. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the MCP queries from the Verification section to confirm the signals returned to expected ranges. A fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from Kubernetes Cluster State
list_metrics with optional filter by context prefix

# Pull a specific signal over the last window
query_metrics with context=<signal>, relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with host=<host> or service=<service>

# Correlate a known problem signal with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating Kubernetes Cluster State as a generic HTTP or process health check. Kubernetes Cluster State has specific failure archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed Kubernetes Cluster State traffic before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the Kubernetes Cluster State service:

```text
1. list_metrics filtered by the Kubernetes Cluster State service's context prefix.
2. query_metrics for the key signals from the first-triggered domain over the last 30 minutes.
3. find_anomalous_metrics scoped to the same service/time window.
```

Signals the playbook considers load-bearing:

  - API Server Health
  - etcd Leader Existence
  - Controller Manager Health
  - API Server Request Latency (P99)
  - etcd WAL Fsync Latency
  - etcd Backend Commit Latency

A clean result means every key signal is within its expected band and the `find_anomalous_metrics` list is empty or contains only already-acknowledged items. If the fix was real, re-running the same queries 10 minutes after applying it will show a clean result. If it does not, revert and look deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was deeper than the applied change. Typical misdiagnoses for Kubernetes Cluster State:

- Host-resource pressure masquerading as application bug.
- Dependent service (DB, cache, upstream) causing a secondary symptom in the instrumented service.
- Configuration change that was never reloaded (some subsystems only pick up config on full restart).

Escalate by widening the query window: 2-6 hours instead of 15 minutes. Slow-moving causes are invisible at triage window sizes.

## References

- [`rules/control-plane-availability.md`](./rules/control-plane-availability.md)
- [`rules/control-plane-performance.md`](./rules/control-plane-performance.md)
- [`rules/etcd-health.md`](./rules/etcd-health.md)
- [`rules/node-health.md`](./rules/node-health.md)
- [`rules/kubelet-health.md`](./rules/kubelet-health.md)
- [`rules/pod-lifecycle.md`](./rules/pod-lifecycle.md)
- [`rules/workload-health.md`](./rules/workload-health.md)
- [`rules/storage.md`](./rules/storage.md)
- [`rules/dns.md`](./rules/dns.md)
- [`rules/certificates.md`](./rules/certificates.md)
- [`rules/resource-utilization.md`](./rules/resource-utilization.md)
- [`rules/events-observability.md`](./rules/events-observability.md)
- [`rules/security-integrity.md`](./rules/security-integrity.md)
- Netdata operator playbook: the authoritative source material this skill summarizes.
- `skills/netdata-mcp-integration/` for the transport setup.
- `skills/netdata-otel-setup/` if additional application signals are needed beyond what Netdata collects natively.
