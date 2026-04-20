---
name: troubleshoot-varnish
description: "Use when diagnosing issues with Varnish Cache: thread pool exhaustion, cache stampede (thundering herd), ban list explosion, storage exhaustion, or workspace overflow. Queries Netdata via MCP for session and request drop rate, backend health state, cache hit ratio, backend request rate, thread pool saturation, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - varnish
---

# Troubleshoot Varnish Cache

## When to use this skill

- **Thread pool exhaustion**: All workers busy, queue fills, sessions/requests dropped. CPU may be
                              idle while Varnish refuses connections. Root cause is usually slow
                              backends holding threads or undersized `thread_pool_max`.
- **Cache stampede (thundering herd)**: A popular cached object expires. Hundreds of concurrent
                                        requests all miss, all fetch from backend simultaneously.
                                        Backend overwhelmed. Without grace/stale-while-revalidate,
                                        this cascades into backend overload.
- **Ban list explosion**: Application logic issues bans faster than the ban lurker can process them.
                          Ban list grows unbounded, cache lookups become O(n) on the ban list,
                          latency spikes across all requests.
- **Storage exhaustion**: The malloc/file storage fills. Aggressive LRU eviction begins, hit rate
                          drops, backend load surges. With malloc, the cliff is sudden; once
                          `g_space` reaches 0, allocation failures cause either object eviction or
                          allocation failures.
- **Workspace overflow**: HTTP headers or cookies exceed workspace allocation. Requests fail with
                          500 errors. Often caused by large `Cookie` or `Set-Cookie` headers.
- **Child process crash loop**: The child process panics, dumps core, and the management process
                                restarts it. Cache is lost on each restart. Repeated crash-restart
                                cycles mean zero effective caching.
- Any time the user reports a Varnish Cache service behaving outside its expected envelope (elevated
  errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a Varnish Cache instance and wants a
  structured triage path.

## Key facts

- This skill wraps the Netdata operator playbook for Varnish Cache. It does not replace the
  playbook; it routes a coding agent through MCP queries against the same signals the playbook
  relies on.
- Varnish Cache is a reverse HTTP proxy that serves cached content from memory at near-wire speed.
  It uses a dual-process architecture: a **management process** (root-owned, handles VCL
  compilation, child supervision, CLI) and a **worker/child process** (drops privileges, handles all
  cache operations). Understanding this split is essential; the management process can restart the
  child automatical...
- The playbook decomposes Varnish Cache health into 6 signal domains: Availability, Throughput &
  Efficiency, Saturation & Resources, Internal State, Backend Connections, Security & Integrity.
  Each domain maps to one rule file in this skill.
- Dominant failure archetypes the playbook calls out: Thread pool exhaustion; Cache stampede
  (thundering herd); Ban list explosion; Storage exhaustion; Workspace overflow.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your Varnish Cache instrumentation adds. Both paths end at the
  same MCP query surface.
- Netdata's varnish collector emits 16 context(s) under `varnish.*`. The rule files enumerate which
  contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the Varnish Cache service is up. Query Netdata via MCP with `list_nodes` and filter by
   the host running the target. A missing node means the symptom is at the network or orchestrator
   layer, not inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **Thread pool exhaustion**. All workers busy, queue fills, sessions/requests dropped.
   CPU may be idle while Varnish refuses connections. Root cause is usually slow backends holding
   threads or undersized `thread_pool_max`. Inspect the rule file whose signals move first for this
   mode.
4. Check for **Cache stampede (thundering herd)**. A popular cached object expires. Hundreds of
   concurrent requests all miss, all fetch from backend simultaneously. Backend overwhelmed. Without
   grace/stale-while-revalidate, this cascades into backend overload. Inspect the rule file whose
   signals move first for this mode.
5. Check for **Ban list explosion**. Application logic issues bans faster than the ban lurker can
   process them. Ban list grows unbounded, cache lookups become O(n) on the ban list, latency spikes
   across all requests. Inspect the rule file whose signals move first for this mode.
6. Check for **Storage exhaustion**. The malloc/file storage fills. Aggressive LRU eviction begins,
   hit rate drops, backend load surges. With malloc, the cliff is sudden; once `g_space` reaches 0,
   allocation failures cause either object eviction or allocation failures. Inspect the rule file
   whose signals move first for this mode.
7. Check for **Workspace overflow**. HTTP headers or cookies exceed workspace allocation. Requests
   fail with 500 errors. Often caused by large `Cookie` or `Set-Cookie` headers. Inspect the rule
   file whose signals move first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from Varnish Cache
list_metrics with q="varnish"

# Pull a specific context over the last window
query_metrics with context="varnish.client_session_connections", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="varnish.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating Varnish Cache as a generic HTTP or process health check. Varnish Cache has specific
  failure archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed Varnish Cache traffic
  before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the Varnish Cache service. Every
context listed below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="varnish" (returns every varnish.* context Netdata sees)
2. query_metrics with contexts=[varnish.client_session_connections, varnish.mgmt_process_uptime, varnish.child_process_uptime, varnish.thread_management_activity, varnish.esi_parsing_issues, varnish.client_requests] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="varnish.*"
```

Load-bearing contexts for this service:

- `varnish.client_session_connections`: Connections Statistics (connections/s). Dimensions:
                                        accepted, dropped.
- `varnish.mgmt_process_uptime`: Management Process Uptime (seconds). Dimensions: uptime.
- `varnish.child_process_uptime`: Child Process Uptime (seconds). Dimensions: uptime.
- `varnish.thread_management_activity`: Thread Management Activity (threads/s). Dimensions: created,
                                        failed, destroyed, limited.
- `varnish.esi_parsing_issues`: ESI Parsing Issues (issues/s). Dimensions: errors, warnings.
- `varnish.client_requests`: Client Requests (requests/s). Dimensions: received.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for Varnish Cache:

- Host-resource pressure masquerading as application bug.
- Dependent service (DB, cache, upstream) causing a secondary symptom in the instrumented service.
- Configuration change that was never reloaded (some subsystems only pick up config on full
  restart).

Escalate by widening the query window: 2-6 hours instead of 15 minutes. Slow-moving causes are
invisible at triage window sizes.

## References

- [`rules/availability.md`](./rules/availability.md)
- [`rules/throughput-efficiency.md`](./rules/throughput-efficiency.md)
- [`rules/saturation-resources.md`](./rules/saturation-resources.md)
- [`rules/internal-state.md`](./rules/internal-state.md)
- [`rules/backend-connections.md`](./rules/backend-connections.md)
- [`rules/security-integrity.md`](./rules/security-integrity.md)
- Netdata operator playbook: the authoritative source material this skill summarizes.
- `skills/netdata-mcp-integration/` for the transport setup.
- `skills/netdata-otel-setup/` if additional application signals are needed beyond what Netdata
  collects natively.
