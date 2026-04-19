---
name: troubleshoot-logstash
description: "Use when diagnosing issues with Logstash: Logstash operational issues. Queries Netdata via MCP for Logstash health signals, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - logstash
---

# Troubleshoot Logstash

## When to use this skill

- Any time the user reports a Logstash service behaving outside its expected envelope (elevated
  errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a Logstash instance and wants a
  structured triage path.

## Key facts

- This skill wraps the Netdata operator playbook for Logstash. It does not replace the playbook; it
  routes a coding agent through MCP queries against the same signals the playbook relies on.
- Logstash is a JVM-based event processing pipeline runner. At its core, it is a queue-backed,
  multi-threaded batch processor with a plugin architecture. Understanding its internal flow is
  essential for reasoning about failures:
- ``` [Input Plugins] then [Codec] then [Queue] then [Worker Threads] then [Filter Chain] then
  [Codec] then [Output Plugins] ↑ | |__________ backpressure propagation ←←←←←←←←←←←←←←←←←←←←| ```
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your Logstash instrumentation adds. Both paths end at the same
  MCP query surface.
- Netdata's logstash collector emits 14 context(s) under `logstash.*`. The rule files enumerate
  which contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the Logstash service is up. Query Netdata via MCP with `list_nodes` and filter by the
   host running the target. A missing node means the symptom is at the network or orchestrator
   layer, not inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
4. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from Logstash
list_metrics with q="logstash"

# Pull a specific context over the last window
query_metrics with context="logstash.uptime", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="logstash.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating Logstash as a generic HTTP or process health check. Logstash has specific failure
  archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed Logstash traffic
  before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the Logstash service. Every context
listed below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="logstash" (returns every logstash.* context Netdata sees)
2. query_metrics with contexts=[logstash.uptime, logstash.jvm_mem_heap_used, logstash.jvm_mem_heap, logstash.jvm_mem_pools_eden, logstash.jvm_mem_pools_survivor, logstash.jvm_mem_pools_old] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="logstash.*"
```

Load-bearing contexts for this service:

- `logstash.uptime`: Uptime (seconds). Dimensions: uptime.
- `logstash.jvm_mem_heap_used`: JVM Heap Memory Percentage (percentage). Dimensions: in_use.
- `logstash.jvm_mem_heap`: JVM Heap Memory (KiB). Dimensions: committed, used.
- `logstash.jvm_mem_pools_eden`: JVM Pool Eden Memory (KiB). Dimensions: committed, used.
- `logstash.jvm_mem_pools_survivor`: JVM Pool Survivor Memory (KiB). Dimensions: committed, used.
- `logstash.jvm_mem_pools_old`: JVM Pool Old Memory (KiB). Dimensions: committed, used.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for Logstash:

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
