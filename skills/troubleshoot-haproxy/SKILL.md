---
name: troubleshoot-haproxy
description: "Use when diagnosing issues with HAProxy: connection saturation, backend collapse, tls resource exhaustion, buffer starvation, or reload storms. Queries Netdata via MCP for process liveness, backend server health status, frontend session rate, http request rate, queue time (qtime), applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - haproxy
---

# Troubleshoot HAProxy

## When to use this skill

- **Connection saturation**: global `maxconn` or per-server/per-backend `maxconn` reached. New
                             connections queue or are rejected. The system appears responsive
                             (HAProxy is alive) but clients experience delays or 503 errors. This is
                             the single most common operational issue.
- **Backend collapse**: health checks detect server failures, traffic concentrates on remaining
                        servers, those become overloaded, their health checks fail, cascade.
                        Eventually all servers marked DOWN, HAProxy returns 503 to all requests.
- **TLS resource exhaustion**: high rate of new TLS connections (no session reuse) saturates CPU.
                               Throughput drops, latency spikes, but HAProxy doesn't crash; it just
                               can't complete handshakes fast enough.
- **Buffer starvation**: under extreme concurrency with large requests/responses, the buffer pool is
                         exhausted. Connections stall waiting for buffers. Manifests as mysterious
                         latency spikes with no CPU/network explanation. `PoolFailed` counter
                         confirms.
- **Reload storms**: frequent config reloads cause old processes to linger while draining, consuming
                     file descriptors and memory. New processes compete for listener sockets. Stats
                     counters reset on each reload.
- **Stick-table overflow**: table reaches configured size. With default settings, expired entries
                            are evicted via LRU to make room (silent). With `nopurge`, new entries
                            are rejected. In both cases, rate-limiting and persistence logic may
                            stop working for affected clients.
- Any time the user reports a HAProxy service behaving outside its expected envelope (elevated
  errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a HAProxy instance and wants a structured
  triage path.

## Key facts

- This skill wraps the Netdata operator playbook for HAProxy. It does not replace the playbook; it
  routes a coding agent through MCP queries against the same signals the playbook relies on.
- HAProxy is an event-driven, Layer 4 (TCP) and Layer 7 (HTTP/HTTPS) proxy and load balancer. It
  accepts connections on **frontends**, applies ACL rules to route them to **backends**, and
  forwards traffic to individual **servers** within those backends. The core event loop uses the
  kernel's most efficient poller (`epoll` on Linux) to multiplex potentially hundreds of thousands
  of concurrent conne...
- The playbook decomposes HAProxy health into 7 signal domains: Availability, Throughput, Latency,
  Errors, Saturation, Ssl/Tls. Each domain maps to one rule file in this skill.
- Dominant failure archetypes the playbook calls out: Connection saturation; Backend collapse; TLS
  resource exhaustion; Buffer starvation; Reload storms.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your HAProxy instrumentation adds. Both paths end at the same
  MCP query surface.
- Netdata's haproxy collector emits 7 context(s) under `haproxy.*`. The rule files enumerate which
  contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the HAProxy service is up. Query Netdata via MCP with `list_nodes` and filter by the host
   running the target. A missing node means the symptom is at the network or orchestrator layer, not
   inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **Connection saturation**. global `maxconn` or per-server/per-backend `maxconn`
   reached. New connections queue or are rejected. The system appears responsive (HAProxy is alive)
   but clients experience delays or 503 errors. This is the single most common operational issue.
   Inspect the rule file whose signals move first for this mode.
4. Check for **Backend collapse**. health checks detect server failures, traffic concentrates on
   remaining servers, those become overloaded, their health checks fail, cascade. Eventually all
   servers marked DOWN, HAProxy returns 503 to all requests. Inspect the rule file whose signals
   move first for this mode.
5. Check for **TLS resource exhaustion**. high rate of new TLS connections (no session reuse)
   saturates CPU. Throughput drops, latency spikes, but HAProxy doesn't crash; it just can't
   complete handshakes fast enough. Inspect the rule file whose signals move first for this mode.
6. Check for **Buffer starvation**. under extreme concurrency with large requests/responses, the
   buffer pool is exhausted. Connections stall waiting for buffers. Manifests as mysterious latency
   spikes with no CPU/network explanation. `PoolFailed` counter confirms. Inspect the rule file
   whose signals move first for this mode.
7. Check for **Reload storms**. frequent config reloads cause old processes to linger while
   draining, consuming file descriptors and memory. New processes compete for listener sockets.
   Stats counters reset on each reload. Inspect the rule file whose signals move first for this
   mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from HAProxy
list_metrics with q="haproxy"

# Pull a specific context over the last window
query_metrics with context="haproxy.backend_response_time_average", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="haproxy.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating HAProxy as a generic HTTP or process health check. HAProxy has specific failure
  archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed HAProxy traffic
  before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the HAProxy service. Every context
listed below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="haproxy" (returns every haproxy.* context Netdata sees)
2. query_metrics with contexts=[haproxy.backend_response_time_average, haproxy.backend_queue_time_average, haproxy.backend_sessions, haproxy.backend_current_queue, haproxy.backend_network_io, haproxy.backend_current_sessions] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="haproxy.*"
```

Load-bearing contexts for this service:

- `haproxy.backend_response_time_average`: Average response time for last 1024 successful
                                           connections (milliseconds).
- `haproxy.backend_queue_time_average`: Average queue time for last 1024 successful connections
                                        (milliseconds).
- `haproxy.backend_sessions`: Sessions rate (sessions/s).
- `haproxy.backend_current_queue`: Current number of queued requests (requests).
- `haproxy.backend_network_io`: Network traffic (bytes/s). Dimensions: in, out.
- `haproxy.backend_current_sessions`: Current number of active sessions (sessions).

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for HAProxy:

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
- [`rules/saturation.md`](./rules/saturation.md)
- [`rules/ssltls.md`](./rules/ssltls.md)
- [`rules/configuration-operational.md`](./rules/configuration-operational.md)
- Netdata operator playbook: the authoritative source material this skill summarizes.
- `skills/netdata-mcp-integration/` for the transport setup.
- `skills/netdata-otel-setup/` if additional application signals are needed beyond what Netdata
  collects natively.
