---
name: troubleshoot-php-fpm
description: "Use when diagnosing issues with PHP-FPM: worker exhaustion, slow request cascade, memory leak spiral, socket backlog overflow, or session lock serialization. Queries Netdata via MCP for service liveness (ping/health check), listen queue depth, active worker count, slow requests, per-worker request duration, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - php-fpm
---

# Troubleshoot PHP-FPM

## When to use this skill

- **Worker exhaustion**: All `pm.max_children` slots occupied. New requests queue in the socket
                         backlog. Once backlog fills, connections are refused. Users see 502/504.
- **Slow request cascade**: A subset of requests block on slow backends (database, external API).
                            These tie up workers for extended periods, reducing effective
                            concurrency for all other requests. Throughput collapses even though CPU
                            may be low.
- **Memory leak spiral**: Workers accumulate memory over time (especially when `pm.max_requests` is
                          0/unlimited). Eventually OOM killer strikes, taking out workers or the
                          master. Restarting fixes it temporarily but it recurs.
- **Socket backlog overflow**: Even with free workers, if the connection arrival rate exceeds the
                               rate at which workers can accept(), the kernel backlog fills. This is
                               rare in normal operation but happens during SYN floods or massive
                               burst traffic.
- **Session lock serialization**: With file-based sessions, concurrent requests from the same user
                                  block on `flock(LOCK_EX)`. AJAX-heavy pages or parallel API calls
                                  from the same session ID serialize completely, appearing as
                                  slowness.
- **Cold start penalty**: After restart or in `ondemand` mode, opcache is empty. Every request
                          compiles PHP from source, causing high CPU and slow responses until the
                          cache warms.
- Any time the user reports a PHP-FPM service behaving outside its expected envelope (elevated
  errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a PHP-FPM instance and wants a structured
  triage path.

## Key facts

- This skill wraps the Netdata operator playbook for PHP-FPM. It does not replace the playbook; it
  routes a coding agent through MCP queries against the same signals the playbook relies on.
- PHP-FPM (FastCGI Process Manager) is a **process-based concurrency model** with a master-worker
  architecture. The master process manages one or more **pools** of worker processes. Each worker
  handles **exactly one request at a time**; there is no in-process concurrency. This is the single
  most important fact: maximum concurrent request capacity equals the number of active worker
  processes.
- The playbook decomposes PHP-FPM health into 8 signal domains: Availability & Liveness, Saturation
  & Capacity, Performance & Latency, Resource Utilization, Process Lifecycle, Connectivity. Each
  domain maps to one rule file in this skill.
- Dominant failure archetypes the playbook calls out: Worker exhaustion; Slow request cascade;
  Memory leak spiral; Socket backlog overflow; Session lock serialization.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your PHP-FPM instrumentation adds. Both paths end at the same
  MCP query surface.
- Netdata's phpfpm collector emits 6 context(s) under `phpfpm.*`. The rule files enumerate which
  contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the PHP-FPM service is up. Query Netdata via MCP with `list_nodes` and filter by the host
   running the target. A missing node means the symptom is at the network or orchestrator layer, not
   inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **Worker exhaustion**. All `pm.max_children` slots occupied. New requests queue in the
   socket backlog. Once backlog fills, connections are refused. Users see 502/504. Inspect the rule
   file whose signals move first for this mode.
4. Check for **Slow request cascade**. A subset of requests block on slow backends (database,
   external API). These tie up workers for extended periods, reducing effective concurrency for all
   other requests. Throughput collapses even though CPU may be low. Inspect the rule file whose
   signals move first for this mode.
5. Check for **Memory leak spiral**. Workers accumulate memory over time (especially when
   `pm.max_requests` is 0/unlimited). Eventually OOM killer strikes, taking out workers or the
   master. Restarting fixes it temporarily but it recurs. Inspect the rule file whose signals move
   first for this mode.
6. Check for **Socket backlog overflow**. Even with free workers, if the connection arrival rate
   exceeds the rate at which workers can accept(), the kernel backlog fills. This is rare in normal
   operation but happens during SYN floods or massive burst traffic. Inspect the rule file whose
   signals move first for this mode.
7. Check for **Session lock serialization**. With file-based sessions, concurrent requests from the
   same user block on `flock(LOCK_EX)`. AJAX-heavy pages or parallel API calls from the same session
   ID serialize completely, appearing as slowness. Inspect the rule file whose signals move first
   for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from PHP-FPM
list_metrics with q="phpfpm"

# Pull a specific context over the last window
query_metrics with context="phpfpm.connections", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="phpfpm.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating PHP-FPM as a generic HTTP or process health check. PHP-FPM has specific failure
  archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed PHP-FPM traffic
  before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the PHP-FPM service. Every context
listed below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="phpfpm" (returns every phpfpm.* context Netdata sees)
2. query_metrics with contexts=[phpfpm.connections, phpfpm.requests, phpfpm.performance, phpfpm.request_duration, phpfpm.request_cpu, phpfpm.request_mem] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="phpfpm.*"
```

Load-bearing contexts for this service:

- `phpfpm.connections`: Active Connections (connections). Dimensions: active, max_active, idle.
- `phpfpm.requests`: Requests (requests/s). Dimensions: requests.
- `phpfpm.performance`: Performance (status). Dimensions: max_children_reached, slow_requests.
- `phpfpm.request_duration`: Requests Duration Among All Idle Processes (milliseconds). Dimensions:
                             min, max, avg.
- `phpfpm.request_cpu`: Last Request CPU Usage Among All Idle Processes (percentage). Dimensions:
                        min, max, avg.
- `phpfpm.request_mem`: Last Request Memory Usage Among All Idle Processes (KB). Dimensions: min,
                        max, avg.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for PHP-FPM:

- Host-resource pressure masquerading as application bug.
- Dependent service (DB, cache, upstream) causing a secondary symptom in the instrumented service.
- Configuration change that was never reloaded (some subsystems only pick up config on full
  restart).

Escalate by widening the query window: 2-6 hours instead of 15 minutes. Slow-moving causes are
invisible at triage window sizes.

## References

- [`rules/availability-liveness.md`](./rules/availability-liveness.md)
- [`rules/saturation-capacity.md`](./rules/saturation-capacity.md)
- [`rules/performance-latency.md`](./rules/performance-latency.md)
- [`rules/resource-utilization.md`](./rules/resource-utilization.md)
- [`rules/process-lifecycle.md`](./rules/process-lifecycle.md)
- [`rules/connectivity.md`](./rules/connectivity.md)
- [`rules/internal-state.md`](./rules/internal-state.md)
- [`rules/security-integrity.md`](./rules/security-integrity.md)
- Netdata operator playbook: the authoritative source material this skill summarizes.
- `skills/netdata-mcp-integration/` for the transport setup.
- `skills/netdata-otel-setup/` if additional application signals are needed beyond what Netdata
  collects natively.
