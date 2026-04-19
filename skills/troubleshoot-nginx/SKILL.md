---
name: troubleshoot-nginx
description: "Use when diagnosing issues with nginx: connection exhaustion, file descriptor exhaustion, backend cascade failure, buffer spill to disk, or ssl cpu saturation. Queries Netdata via MCP for worker process count, stub status endpoint availability, requests per second, active connections, request processing time, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - nginx
---

# Troubleshoot nginx

## When to use this skill

- **Connection exhaustion**: All `worker_connections` slots consumed. New connections dropped or
                             queued at kernel listen backlog. Often caused by slow backends holding
                             connections open.
- **File descriptor exhaustion**: Hit system or configured limit. Manifests as "too many open files"
                                  errors; can't accept connections, can't open logs, can't connect
                                  to upstreams.
- **Backend cascade failure**: Upstreams slow or unresponsive. Workers pile up waiting connections.
                               nginx appears "down" even though nginx itself is fine.
- **Buffer spill to disk**: Large request/response bodies exceed configured buffers. nginx writes to
                            temp files. Disk I/O spikes. Latency explodes. Silent; no error log
                            entries.
- **SSL CPU saturation**: Heavy TLS handshake load (many short-lived connections) consumes CPU
                          faster than workers can serve content.
- **DNS resolution failure**: Dynamic upstreams using variables cause per-request DNS lookups via
                              async resolver. DNS timeout (default 30s) becomes request latency.
                              Returns 502.
- Any time the user reports a nginx service behaving outside its expected envelope (elevated errors,
  latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a nginx instance and wants a structured
  triage path.

## Key facts

- This skill wraps the Netdata operator playbook for nginx. It does not replace the playbook; it
  routes a coding agent through MCP queries against the same signals the playbook relies on.
- nginx is an event-driven, non-blocking, single-threaded-per-worker process architecture.
  Understanding this is the foundation of everything that follows.
- The playbook decomposes nginx health into 11 signal domains: Availability, Throughput, Latency,
  Errors, Saturation & Resource Utilization, Upstream Health. Each domain maps to one rule file in
  this skill.
- Dominant failure archetypes the playbook calls out: Connection exhaustion; File descriptor
  exhaustion; Backend cascade failure; Buffer spill to disk; SSL CPU saturation.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your nginx instrumentation adds. Both paths end at the same MCP
  query surface.
- Netdata's nginx collector emits 4 context(s) under `nginx.*`. The rule files enumerate which
  contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the nginx service is up. Query Netdata via MCP with `list_nodes` and filter by the host
   running the target. A missing node means the symptom is at the network or orchestrator layer, not
   inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **Connection exhaustion**. All `worker_connections` slots consumed. New connections
   dropped or queued at kernel listen backlog. Often caused by slow backends holding connections
   open. Inspect the rule file whose signals move first for this mode.
4. Check for **File descriptor exhaustion**. Hit system or configured limit. Manifests as "too many
   open files" errors; can't accept connections, can't open logs, can't connect to upstreams.
   Inspect the rule file whose signals move first for this mode.
5. Check for **Backend cascade failure**. Upstreams slow or unresponsive. Workers pile up waiting
   connections. nginx appears "down" even though nginx itself is fine. Inspect the rule file whose
   signals move first for this mode.
6. Check for **Buffer spill to disk**. Large request/response bodies exceed configured buffers.
   nginx writes to temp files. Disk I/O spikes. Latency explodes. Silent; no error log entries.
   Inspect the rule file whose signals move first for this mode.
7. Check for **SSL CPU saturation**. Heavy TLS handshake load (many short-lived connections)
   consumes CPU faster than workers can serve content. Inspect the rule file whose signals move
   first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from nginx
list_metrics with q="nginx"

# Pull a specific context over the last window
query_metrics with context="nginx.connections", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="nginx.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating nginx as a generic HTTP or process health check. nginx has specific failure archetypes
  (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed nginx traffic before
  escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the nginx service. Every context listed
below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="nginx" (returns every nginx.* context Netdata sees)
2. query_metrics with contexts=[nginx.connections, nginx.connections_status, nginx.connections_accepted_handled, nginx.requests] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="nginx.*"
```

Load-bearing contexts for this service:

- `nginx.connections`: Active Client Connections Including Waiting Connections (connections).
                       Dimensions: active.
- `nginx.connections_status`: Active Connections Per Status (connections). Dimensions: reading,
                              writing, idle.
- `nginx.connections_accepted_handled`: Accepted And Handled Connections (connections/s).
                                        Dimensions: accepted, handled.
- `nginx.requests`: Client Requests (requests/s). Dimensions: requests.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for nginx:

- Host-resource pressure masquerading as application bug.
- Dependent service (DB, cache, upstream) causing a secondary symptom in the instrumented service.
- Configuration change that was never reloaded (some subsystems only pick up config on full
  restart).

Escalate by widening the query window: 2-6 hours instead of 15 minutes. Slow-moving causes are
invisible at triage window sizes.

## References

- [`rules/availability.md`](./rules/availability.md)
- [`rules/throughput.md`](./rules/throughput.md)
- [`rules/latency.md`](./rules/latency.md)
- [`rules/errors.md`](./rules/errors.md)
- [`rules/saturation-resource-utilization.md`](./rules/saturation-resource-utilization.md)
- [`rules/upstream-health.md`](./rules/upstream-health.md)
- [`rules/ssltls.md`](./rules/ssltls.md)
- [`rules/configuration-lifecycle.md`](./rules/configuration-lifecycle.md)
- [`rules/caching-if-enabled.md`](./rules/caching-if-enabled.md)
- [`rules/rate-limiting.md`](./rules/rate-limiting.md)
- [`rules/dns-resolution-dynamic-upstreams.md`](./rules/dns-resolution-dynamic-upstreams.md)
- Netdata operator playbook: the authoritative source material this skill summarizes.
- `skills/netdata-mcp-integration/` for the transport setup.
- `skills/netdata-otel-setup/` if additional application signals are needed beyond what Netdata
  collects natively.
