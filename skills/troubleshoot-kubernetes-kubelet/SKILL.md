---
name: troubleshoot-kubernetes-kubelet
description: "Use when diagnosing issues with Kubernetes Kubelet: pleg stall, resource pressure cascade, api server disconnection, volume mount stuck, or silent new-pod outage. Queries Netdata via MCP for Kubernetes Kubelet health signals, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - kubernetes-kubelet
---

# Troubleshoot Kubernetes Kubelet

## When to use this skill

- **PLEG Stall**: Container runtime becomes slow. PLEG relist exceeds 3 minutes. Node goes NotReady.
                  The #1 cause of unexpected NotReady nodes.
- **Resource Pressure Cascade**: Node runs low on memory/disk/PIDs. Eviction manager starts killing
                                 pods. Killed pods get rescheduled, possibly back to the same node.
                                 The node oscillates between pressure/no-pressure.
- **API Server Disconnection**: Network partition, API server overload, or certificate expiry.
                                Kubelet continues running existing pods autonomously but cannot
                                receive new pods or report status. After ~350 seconds (50s grace +
                                300s toleration), pods are rescheduled elsewhere.
- **Volume Mount Stuck**: CSI driver or NFS mount hangs. Affected pods hang in ContainerCreating.
                          Volume manager goroutines are blocked. Node appears healthy but pods with
                          volumes stall.
- **Silent New-Pod Outage**: Node is Ready, existing pods run fine, but new pods cannot start due to
                             CNI failure, IPAM exhaustion, image pull failure, or CSI breakage.
                             Classic partial outage.
- **Kubelet OOM**: On very busy nodes, kubelet's own memory grows until the OOM killer targets it.
                   Brief node NotReady, followed by a full reconciliation storm on restart.
- Any time the user reports a Kubernetes Kubelet service behaving outside its expected envelope
  (elevated errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a Kubernetes Kubelet instance and wants a
  structured triage path.

## Key facts

- This skill wraps the Netdata operator playbook for Kubernetes Kubelet. It does not replace the
  playbook; it routes a coding agent through MCP queries against the same signals the playbook
  relies on.
- Kubelet is the node-level agent that makes Kubernetes real. Everything above it; API server,
  scheduler, controllers; deals in intent. Kubelet deals in reality: it receives pod specifications
  and turns them into running containers on a specific Linux machine.
- Dominant failure archetypes the playbook calls out: PLEG Stall; Resource Pressure Cascade; API
  Server Disconnection; Volume Mount Stuck; Silent New-Pod Outage.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your Kubernetes Kubelet instrumentation adds. Both paths end at
  the same MCP query surface.
- Netdata's k8s_kubelet collector emits 19 context(s) under `k8s_kubelet.*`. The rule files
  enumerate which contexts surface which domain; the Verification section below names the
  load-bearing ones explicitly.

## Step-by-step

1. Confirm the Kubernetes Kubelet service is up. Query Netdata via MCP with `list_nodes` and filter
   by the host running the target. A missing node means the symptom is at the network or
   orchestrator layer, not inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **PLEG Stall**. Container runtime becomes slow. PLEG relist exceeds 3 minutes. Node
   goes NotReady. The #1 cause of unexpected NotReady nodes. Inspect the rule file whose signals
   move first for this mode.
4. Check for **Resource Pressure Cascade**. Node runs low on memory/disk/PIDs. Eviction manager
   starts killing pods. Killed pods get rescheduled, possibly back to the same node. The node
   oscillates between pressure/no-pressure. Inspect the rule file whose signals move first for this
   mode.
5. Check for **API Server Disconnection**. Network partition, API server overload, or certificate
   expiry. Kubelet continues running existing pods autonomously but cannot receive new pods or
   report status. After ~350 seconds (50s grace + 300s toleration), pods are rescheduled elsewhere.
   Inspect the rule file whose signals move first for this mode.
6. Check for **Volume Mount Stuck**. CSI driver or NFS mount hangs. Affected pods hang in
   ContainerCreating. Volume manager goroutines are blocked. Node appears healthy but pods with
   volumes stall. Inspect the rule file whose signals move first for this mode.
7. Check for **Silent New-Pod Outage**. Node is Ready, existing pods run fine, but new pods cannot
   start due to CNI failure, IPAM exhaustion, image pull failure, or CSI breakage. Classic partial
   outage. Inspect the rule file whose signals move first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from Kubernetes Kubelet
list_metrics with q="k8s_kubelet"

# Pull a specific context over the last window
query_metrics with context="k8s_kubelet.rest_client_requests_by_code", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="k8s_kubelet.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating Kubernetes Kubelet as a generic HTTP or process health check. Kubernetes Kubelet has
  specific failure archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed Kubernetes Kubelet
  traffic before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the Kubernetes Kubelet service. Every
context listed below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="k8s_kubelet" (returns every k8s_kubelet.* context Netdata sees)
2. query_metrics with contexts=[k8s_kubelet.rest_client_requests_by_code, k8s_kubelet.rest_client_requests_by_method, k8s_kubelet.apiserver_audit_requests_rejected, k8s_kubelet.apiserver_storage_data_key_generation_failures, k8s_kubelet.kubelet_runtime_operations_errors, k8s_kubelet.kubelet_docker_operations_errors] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="k8s_kubelet.*"
```

Load-bearing contexts for this service:

- `k8s_kubelet.rest_client_requests_by_code`: HTTP Requests By Status Code (requests/s).
- `k8s_kubelet.rest_client_requests_by_method`: HTTP Requests By Status Method (requests/s).
- `k8s_kubelet.apiserver_audit_requests_rejected`: API Server Audit Requests (requests/s).
                                                   Dimensions: rejected.
- `k8s_kubelet.apiserver_storage_data_key_generation_failures`: API Server Failed Data Encryption
                                                                Key(DEK) Generation Operations
                                                                (events/s). Dimensions: failures.
- `k8s_kubelet.kubelet_runtime_operations_errors`: Runtime Operations Errors By Type (errors/s).
- `k8s_kubelet.kubelet_docker_operations_errors`: Docker Operations Errors By Type (errors/s).

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for Kubernetes Kubelet:

- Host-resource pressure masquerading as application bug.
- Dependent service (DB, cache, upstream) causing a secondary symptom in the instrumented service.
- Configuration change that was never reloaded (some subsystems only pick up config on full
  restart).

Escalate by widening the query window: 2-6 hours instead of 15 minutes. Slow-moving causes are
invisible at triage window sizes.

## References

- [`rules/overview.md`](./rules/overview.md)
- Netdata operator playbook: the authoritative source material this skill summarizes.
- `skills/netdata-mcp-integration/` for the transport setup.
- `skills/netdata-otel-setup/` if additional application signals are needed beyond what Netdata
  collects natively.
