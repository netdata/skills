---
name: troubleshoot-kubernetes-cluster-state
description: "Use when diagnosing issues with Kubernetes Cluster State: control plane unavailable, control plane slow, reconciliation stall, node failures, or admission blockage. Queries Netdata via MCP for api server health, etcd leader existence, api server request latency (p99), etcd wal fsync latency, etcd leader changes, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
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

- **Control plane unavailable**: etcd quorum loss, API server crash, or certificate expiration. The
                                 cluster cannot schedule, reschedule, or update anything. Running
                                 pods continue but cannot be managed.
- **Control plane slow**: etcd disk latency, API server overload, webhook timeouts. Everything works
                          but with unacceptable delays. Controllers fall behind, causing stale
                          endpoints, missed scaling, delayed rollouts.
- **Reconciliation stall**: A specific controller falls behind (workqueue depth grows). Deployments
                            don't progress, endpoints go stale, garbage collection stops. The
                            cluster "looks healthy" but desired state diverges from actual state
                            silently.
- **Node failures**: Kubelet crash, container runtime hang, network partition from control plane.
                     Nodes become NotReady, pods are evicted, capacity shrinks.
- **Admission blockage**: Webhook service down with `failurePolicy: Fail`. All matching resource
                          creation/modification blocks. The cluster appears "frozen" for those
                          resources.
- **Silent drift**: Certificates approaching expiry, etcd database growing toward quota, IP address
                    pool exhausting, resource requests exceeding allocatable. No immediate symptoms,
                    but a cliff-edge failure is approaching.
- Any time the user reports a Kubernetes Cluster State service behaving outside its expected
  envelope (elevated errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a Kubernetes Cluster State instance and
  wants a structured triage path.

## Key facts

- This skill wraps the Netdata operator playbook for Kubernetes Cluster State. It does not replace
  the playbook; it routes a coding agent through MCP queries against the same signals the playbook
  relies on.
- Kubernetes is a distributed state machine. Every object; Pod, Deployment, Service, Node,
  PersistentVolumeClaim; has a **desired state** (what you declared in YAML) and a **current state**
  (what actually exists). The entire control plane exists to reconcile these two states
  continuously. When monitoring cluster state, you are monitoring the health and velocity of this
  reconciliation loop.
- The playbook decomposes Kubernetes Cluster State health into 13 signal domains: Control Plane
  Availability, Control Plane Performance, Etcd Health, Node Health, Kubelet Health, Pod Lifecycle.
  Each domain maps to one rule file in this skill.
- Dominant failure archetypes the playbook calls out: Control plane unavailable; Control plane slow;
  Reconciliation stall; Node failures; Admission blockage.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your Kubernetes Cluster State instrumentation adds. Both paths
  end at the same MCP query surface.
- Netdata's k8s_state collector emits 47 context(s) under `k8s_state.*`. The rule files enumerate
  which contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the Kubernetes Cluster State service is up. Query Netdata via MCP with `list_nodes` and
   filter by the host running the target. A missing node means the symptom is at the network or
   orchestrator layer, not inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **Control plane unavailable**. etcd quorum loss, API server crash, or certificate
   expiration. The cluster cannot schedule, reschedule, or update anything. Running pods continue
   but cannot be managed. Inspect the rule file whose signals move first for this mode.
4. Check for **Control plane slow**. etcd disk latency, API server overload, webhook timeouts.
   Everything works but with unacceptable delays. Controllers fall behind, causing stale endpoints,
   missed scaling, delayed rollouts. Inspect the rule file whose signals move first for this mode.
5. Check for **Reconciliation stall**. A specific controller falls behind (workqueue depth grows).
   Deployments don't progress, endpoints go stale, garbage collection stops. The cluster "looks
   healthy" but desired state diverges from actual state silently. Inspect the rule file whose
   signals move first for this mode.
6. Check for **Node failures**. Kubelet crash, container runtime hang, network partition from
   control plane. Nodes become NotReady, pods are evicted, capacity shrinks. Inspect the rule file
   whose signals move first for this mode.
7. Check for **Admission blockage**. Webhook service down with `failurePolicy: Fail`. All matching
   resource creation/modification blocks. The cluster appears "frozen" for those resources. Inspect
   the rule file whose signals move first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from Kubernetes Cluster State
list_metrics with q="k8s_state"

# Pull a specific context over the last window
query_metrics with context="k8s_state.node_condition", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="k8s_state.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating Kubernetes Cluster State as a generic HTTP or process health check. Kubernetes Cluster
  State has specific failure archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed Kubernetes Cluster
  State traffic before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the Kubernetes Cluster State service.
Every context listed below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="k8s_state" (returns every k8s_state.* context Netdata sees)
2. query_metrics with contexts=[k8s_state.node_condition, k8s_state.cronjob_jobs_count_by_status, k8s_state.cronjob_last_execution_status, k8s_state.cronjob_suspend_status, k8s_state.pod_status_reason, k8s_state.node_pods_phase] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="k8s_state.*"
```

Load-bearing contexts for this service:

- `k8s_state.node_condition`: Condition status (status). Dimensions: Ready, DiskPressure,
                              MemoryPressure, NetworkUnavailable, PIDPressure.
- `k8s_state.cronjob_jobs_count_by_status`: CronJob Jobs Count by Status (jobs). Dimensions:
                                            completed, failed, running, suspended.
- `k8s_state.cronjob_last_execution_status`: CronJob Last Execution Status (status). Dimensions:
                                             completed, failed.
- `k8s_state.cronjob_suspend_status`: CronJob Suspend Status (status). Dimensions: enabled,
                                      suspended.
- `k8s_state.pod_status_reason`: Status reason (status). Dimensions: Evicted, NodeAffinity,
                                 NodeLost, Shutdown, UnexpectedAdmissionError, Other.
- `k8s_state.node_pods_phase`: Pods phase (pods). Dimensions: running, failed, succeeded, pending.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for Kubernetes Cluster State:

- Host-resource pressure masquerading as application bug.
- Dependent service (DB, cache, upstream) causing a secondary symptom in the instrumented service.
- Configuration change that was never reloaded (some subsystems only pick up config on full
  restart).

Escalate by widening the query window: 2-6 hours instead of 15 minutes. Slow-moving causes are
invisible at triage window sizes.

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
- `skills/netdata-otel-setup/` if additional application signals are needed beyond what Netdata
  collects natively.
