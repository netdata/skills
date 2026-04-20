---
name: troubleshoot-kubernetes-api-server
description: "Use when diagnosing issues with Kubernetes API Server: the webhook stall, the list storm, the etcd latency cascade, the memory cliff, or the rbac/auth slow bleed. Queries Netdata via MCP for Kubernetes API Server health signals, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - kubernetes-api-server
---

# Troubleshoot Kubernetes API Server

## When to use this skill

- **The webhook stall**: A mutating or validating admission webhook becomes slow or unresponsive.
                         Since webhooks are synchronous in the request path, all requests to
                         affected resources queue up. The API server's request concurrency fills,
                         APF queues overflow, and the cluster appears hung; nothing can...
- **The list storm**: Something triggers mass re-lists; a controller restart, a watch cache overflow
                      (410 Gone responses), or a client with a bad list-without-resourceVersion
                      pattern. The API server issues expensive range scans to etcd, pins CPUs
                      serializing results, and saturates network sending m...
- **The etcd latency cascade**: etcd gets slow (disk I/O, compaction, leader election, quorum loss).
                                API server writes pile up. Mutating request latency climbs.
                                Controllers that depend on writes start retrying. Retries amplify
                                load. The API server's APF queues fill. New requests get 429s.
                                Clients retry those...
- **The memory cliff**: Watch cache growth (more objects, more resource types, CRD proliferation)
                        plus Go GC overhead pushes the API server past its memory limit. OOM kill.
                        All watches disconnect. All clients re-list simultaneously. The replacement
                        API server starts under maximum load.
- **The RBAC/auth slow bleed**: Complex RBAC policies with thousands of roles/bindings, or external
                                authentication (OIDC, webhook token auth) with slow identity
                                providers, add per-request latency that accumulates silently until
                                the concurrency limit is reached.
- **The CRD explosion**: Hundreds of CRDs, each with multiple versions, generating watch caches,
                         requiring storage, and expanding the API server's type system. This taxes
                         memory, serialization CPU, and etcd storage proportionally.
- Any time the user reports a Kubernetes API Server service behaving outside its expected envelope
  (elevated errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a Kubernetes API Server instance and
  wants a structured triage path.

## Key facts

- This skill wraps the Netdata operator playbook for Kubernetes API Server. It does not replace the
  playbook; it routes a coding agent through MCP queries against the same signals the playbook
  relies on.
- The Kubernetes API Server (`kube-apiserver`) is an HTTP REST server that serves as the single
  point of serialized access to the cluster's state stored in etcd. Every mutation and every read of
  cluster state; from kubectl commands, controllers, kubelets, custom operators, CI/CD systems,
  service meshes; passes through this process. It is the funnel through which all coordination
  flows.
- Dominant failure archetypes the playbook calls out: The webhook stall; The list storm; The etcd
  latency cascade; The memory cliff; The RBAC/auth slow bleed.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your Kubernetes API Server instrumentation adds. Both paths end
  at the same MCP query surface.
- Netdata's k8s_apiserver collector emits 29 context(s) under `k8s_apiserver.*`. The rule files
  enumerate which contexts surface which domain; the Verification section below names the
  load-bearing ones explicitly.

## Step-by-step

1. Confirm the Kubernetes API Server service is up. Query Netdata via MCP with `list_nodes` and
   filter by the host running the target. A missing node means the symptom is at the network or
   orchestrator layer, not inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **The webhook stall**. A mutating or validating admission webhook becomes slow or
   unresponsive. Since webhooks are synchronous in the request path, all requests to affected
   resources queue up. The API server's request concurrency fills, APF queues overflow, and the
   cluster appears hung; nothing can be created, updated, or deleted. This is the single most common
   catastrophic API server failure in production. Inspect the rule file whose signals move first for
   this mode.
4. Check for **The list storm**. Something triggers mass re-lists; a controller restart, a watch
   cache overflow (410 Gone responses), or a client with a bad list-without-resourceVersion pattern.
   The API server issues expensive range scans to etcd, pins CPUs serializing results, and saturates
   network sending multi-MB responses. Other requests queue behind list processing. Inspect the rule
   file whose signals move first for this mode.
5. Check for **The etcd latency cascade**. etcd gets slow (disk I/O, compaction, leader election,
   quorum loss). API server writes pile up. Mutating request latency climbs. Controllers that depend
   on writes start retrying. Retries amplify load. The API server's APF queues fill. New requests
   get 429s. Clients retry those. The system enters a positive feedback loop. Inspect the rule file
   whose signals move first for this mode.
6. Check for **The memory cliff**. Watch cache growth (more objects, more resource types, CRD
   proliferation) plus Go GC overhead pushes the API server past its memory limit. OOM kill. All
   watches disconnect. All clients re-list simultaneously. The replacement API server starts under
   maximum load. Inspect the rule file whose signals move first for this mode.
7. Check for **The RBAC/auth slow bleed**. Complex RBAC policies with thousands of roles/bindings,
   or external authentication (OIDC, webhook token auth) with slow identity providers, add
   per-request latency that accumulates silently until the concurrency limit is reached. Inspect the
   rule file whose signals move first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from Kubernetes API Server
list_metrics with q="k8s_apiserver"

# Pull a specific context over the last window
query_metrics with context="k8s_apiserver.requests_by_code", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="k8s_apiserver.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating Kubernetes API Server as a generic HTTP or process health check. Kubernetes API Server
  has specific failure archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed Kubernetes API Server
  traffic before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the Kubernetes API Server service.
Every context listed below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="k8s_apiserver" (returns every k8s_apiserver.* context Netdata sees)
2. query_metrics with contexts=[k8s_apiserver.requests_by_code, k8s_apiserver.rest_client_requests_by_code, k8s_apiserver.requests_dropped, k8s_apiserver.audit_events, k8s_apiserver.workqueue_adds, k8s_apiserver.requests_total] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="k8s_apiserver.*"
```

Load-bearing contexts for this service:

- `k8s_apiserver.requests_by_code`: API Server Requests By Status Code (requests/s).
- `k8s_apiserver.rest_client_requests_by_code`: REST Client Requests By Status Code (requests/s).
- `k8s_apiserver.requests_dropped`: API Server Dropped Requests (requests/s). Dimensions: dropped.
- `k8s_apiserver.audit_events`: API Server Audit Events (events/s). Dimensions: events, rejected.
- `k8s_apiserver.workqueue_adds`: Work Queue Adds (items/s). Dimensions: adds, retries.
- `k8s_apiserver.requests_total`: API Server Request Rate (requests/s). Dimensions: requests.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for Kubernetes API Server:

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
