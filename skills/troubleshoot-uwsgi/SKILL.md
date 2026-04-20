---
name: troubleshoot-uwsgi
description: "Use when diagnosing issues with Uwsgi: worker exhaustion, harakiri storm, memory creep, stuck workers, or reload failure. Queries Netdata via MCP for accepting worker count, worker busy ratio, request throughput (delta requests), average response time (avg_rt), worker running time, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - uwsgi
---

# Troubleshoot Uwsgi

## When to use this skill

- **Worker exhaustion**: All workers busy, requests queue in the kernel backlog, then
- **Harakiri storm**: Workers are killed and respawned faster than they can serve
- **Memory creep**: Workers grow over time until OOM-killed or recycled by
- **Stuck workers**: Workers hang on blocking I/O (database lock, slow external call)
- **Reload failure**: `SIGHUP` reload with broken application code leaves zero
- Any time the user reports a Uwsgi service behaving outside its expected envelope (elevated errors,
  latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a Uwsgi instance and wants a structured
  triage path.

## Key facts

- This skill wraps the Netdata operator playbook for Uwsgi. It does not replace the playbook; it
  routes a coding agent through MCP queries against the same signals the playbook relies on.
- The playbook decomposes Uwsgi health into 8 signal domains: Availability, Worker Pool Utilization,
  Latency, Errors & Stability, Memory, Transmitted Data. Each domain maps to one rule file in this
  skill.
- Dominant failure archetypes the playbook calls out: Worker exhaustion; Harakiri storm; Memory
  creep; Stuck workers; Reload failure.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your Uwsgi instrumentation adds. Both paths end at the same MCP
  query surface.
- Netdata's uwsgi collector emits 15 context(s) under `uwsgi.*`. The rule files enumerate which
  contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the Uwsgi service is up. Query Netdata via MCP with `list_nodes` and filter by the host
   running the target. A missing node means the symptom is at the network or orchestrator layer, not
   inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **Worker exhaustion**. All workers busy, requests queue in the kernel backlog, then
   Inspect the rule file whose signals move first for this mode.
4. Check for **Harakiri storm**. Workers are killed and respawned faster than they can serve Inspect
   the rule file whose signals move first for this mode.
5. Check for **Memory creep**. Workers grow over time until OOM-killed or recycled by Inspect the
   rule file whose signals move first for this mode.
6. Check for **Stuck workers**. Workers hang on blocking I/O (database lock, slow external call)
   Inspect the rule file whose signals move first for this mode.
7. Check for **Reload failure**. `SIGHUP` reload with broken application code leaves zero Inspect
   the rule file whose signals move first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from Uwsgi
list_metrics with q="uwsgi"

# Pull a specific context over the last window
query_metrics with context="uwsgi.worker_status", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="uwsgi.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating Uwsgi as a generic HTTP or process health check. Uwsgi has specific failure archetypes
  (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed Uwsgi traffic before
  escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the Uwsgi service. Every context listed
below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="uwsgi" (returns every uwsgi.* context Netdata sees)
2. query_metrics with contexts=[uwsgi.worker_status, uwsgi.worker_request_handling_status, uwsgi.harakiris, uwsgi.worker_harakiris, uwsgi.requests, uwsgi.worker_requests] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="uwsgi.*"
```

Load-bearing contexts for this service:

- `uwsgi.worker_status`: UWSGI Worker Status (status). Dimensions: idle, busy, cheap, pause, sig.
- `uwsgi.worker_request_handling_status`: UWSGI Worker Request Handling Status (status). Dimensions:
                                          accepting, not_accepting.
- `uwsgi.harakiris`: UWSGI Dropped Requests (harakiris/s). Dimensions: harakiris.
- `uwsgi.worker_harakiris`: UWSGI Worker Dropped Requests (harakiris/s). Dimensions: harakiris.
- `uwsgi.requests`: UWSGI Requests (requests/s). Dimensions: requests.
- `uwsgi.worker_requests`: UWSGI Worker Requests (requests/s). Dimensions: requests.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for Uwsgi:

- Host-resource pressure masquerading as application bug.
- Dependent service (DB, cache, upstream) causing a secondary symptom in the instrumented service.
- Configuration change that was never reloaded (some subsystems only pick up config on full
  restart).

Escalate by widening the query window: 2-6 hours instead of 15 minutes. Slow-moving causes are
invisible at triage window sizes.

## References

- [`rules/availability.md`](./rules/availability.md)
- [`rules/worker-pool-utilization.md`](./rules/worker-pool-utilization.md)
- [`rules/latency.md`](./rules/latency.md)
- [`rules/errors-stability.md`](./rules/errors-stability.md)
- [`rules/memory.md`](./rules/memory.md)
- [`rules/transmitted-data.md`](./rules/transmitted-data.md)
- [`rules/subsystem-health.md`](./rules/subsystem-health.md)
- [`rules/signal-control-plane.md`](./rules/signal-control-plane.md)
- Netdata operator playbook: the authoritative source material this skill summarizes.
- `skills/netdata-mcp-integration/` for the transport setup.
- `skills/netdata-otel-setup/` if additional application signals are needed beyond what Netdata
  collects natively.
