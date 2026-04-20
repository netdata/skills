---
name: troubleshoot-fluentd
description: "Use when diagnosing issues with Fluentd: buffer saturation (backpressure), retry storm, memory bloat / oom, poison pill crash loop, or silent data loss. Queries Netdata via MCP for fluentd process alive, monitor agent api responsiveness, input emit records rate, output emit records rate, cumulative flush time, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - fluentd
---

# Troubleshoot Fluentd

## When to use this skill

- **Buffer Saturation (Backpressure)**: Destination slow/unreachable then buffer
- **Retry Storm**: Output fails repeatedly then exponential backoff then queue never
- **Memory Bloat / OOM**: Ruby memory fragmentation, or memory-backed buffers
- **Poison Pill Crash Loop**: Malformed log line causes parser crash then process
- **Silent Data Loss**: Events dropped due to `overflow_action: throw_exception`
- **File Rotation Loss**: Improper handling of logrotate `copytruncate` causes
- Any time the user reports a Fluentd service behaving outside its expected envelope (elevated
  errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a Fluentd instance and wants a structured
  triage path.

## Key facts

- This skill wraps the Netdata operator playbook for Fluentd. It does not replace the playbook; it
  routes a coding agent through MCP queries against the same signals the playbook relies on.
- Fluentd is an event router and log pipeline. It ingests structured and unstructured log events
  from sources (inputs), transforms them through filters, and delivers them to destinations
  (outputs). Every event flows through this path:
- The playbook decomposes Fluentd health into 8 signal domains: Availability, Throughput, Latency,
  Errors, Saturation, Input Health. Each domain maps to one rule file in this skill.
- Dominant failure archetypes the playbook calls out: Buffer Saturation (Backpressure); Retry Storm;
  Memory Bloat / OOM; Poison Pill Crash Loop; Silent Data Loss.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your Fluentd instrumentation adds. Both paths end at the same
  MCP query surface.
- Netdata's fluentd collector emits 3 context(s) under `fluentd.*`. The rule files enumerate which
  contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the Fluentd service is up. Query Netdata via MCP with `list_nodes` and filter by the host
   running the target. A missing node means the symptom is at the network or orchestrator layer, not
   inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **Buffer Saturation (Backpressure)**. Destination slow/unreachable then buffer Inspect
   the rule file whose signals move first for this mode.
4. Check for **Retry Storm**. Output fails repeatedly then exponential backoff then queue never
   Inspect the rule file whose signals move first for this mode.
5. Check for **Memory Bloat / OOM**. Ruby memory fragmentation, or memory-backed buffers Inspect the
   rule file whose signals move first for this mode.
6. Check for **Poison Pill Crash Loop**. Malformed log line causes parser crash then process Inspect
   the rule file whose signals move first for this mode.
7. Check for **Silent Data Loss**. Events dropped due to `overflow_action: throw_exception` Inspect
   the rule file whose signals move first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from Fluentd
list_metrics with q="fluentd"

# Pull a specific context over the last window
query_metrics with context="fluentd.buffer_queue_length", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="fluentd.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating Fluentd as a generic HTTP or process health check. Fluentd has specific failure
  archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed Fluentd traffic
  before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the Fluentd service. Every context
listed below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="fluentd" (returns every fluentd.* context Netdata sees)
2. query_metrics with contexts=[fluentd.buffer_queue_length, fluentd.buffer_total_queued_size, fluentd.retry_count] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="fluentd.*"
```

Load-bearing contexts for this service:

- `fluentd.buffer_queue_length`: Plugin Buffer Queue Length (queue_length).
- `fluentd.buffer_total_queued_size`: Plugin Buffer Total Size (queued_size).
- `fluentd.retry_count`: Plugin Retry Count (count).

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for Fluentd:

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
- [`rules/input-health.md`](./rules/input-health.md)
- [`rules/resource-pressure.md`](./rules/resource-pressure.md)
- [`rules/security-integrity.md`](./rules/security-integrity.md)
- Netdata operator playbook: the authoritative source material this skill summarizes.
- `skills/netdata-mcp-integration/` for the transport setup.
- `skills/netdata-otel-setup/` if additional application signals are needed beyond what Netdata
  collects natively.
