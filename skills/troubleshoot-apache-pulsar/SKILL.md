---
name: troubleshoot-apache-pulsar
description: "Use when diagnosing issues with Apache Pulsar: availability, latency, saturation & resource utilization, or backlog & consumer health degradation. Queries Netdata via MCP for broker process health, bookie process health, bookie journal sync latency, metadata store request latency, bookie add entry in-progress count, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - apache-pulsar
---

# Troubleshoot Apache Pulsar

## When to use this skill

- Any time the user reports a Apache Pulsar service behaving outside its expected envelope (elevated
  errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a Apache Pulsar instance and wants a
  structured triage path.

## Key facts

- This skill wraps the Netdata operator playbook for Apache Pulsar. It does not replace the
  playbook; it routes a coding agent through MCP queries against the same signals the playbook
  relies on.
- Apache Pulsar is a distributed messaging system with a **two-layer architecture** that
  fundamentally shapes how you monitor it. Understanding this separation is the single most
  important prerequisite before looking at any signal.
- The playbook decomposes Apache Pulsar health into 9 signal domains: Availability, Latency,
  Saturation & Resource Utilization, Backlog & Consumer Health, Replication & Consistency, Resource
  Pressure. Each domain maps to one rule file in this skill.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your Apache Pulsar instrumentation adds. Both paths end at the
  same MCP query surface.
- Netdata's pulsar collector emits 47 context(s) under `pulsar.*`. The rule files enumerate which
  contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the Apache Pulsar service is up. Query Netdata via MCP with `list_nodes` and filter by
   the host running the target. A missing node means the symptom is at the network or orchestrator
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
# Discover metrics from Apache Pulsar
list_metrics with q="pulsar"

# Pull a specific context over the last window
query_metrics with context="pulsar.messages_rate", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="pulsar.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating Apache Pulsar as a generic HTTP or process health check. Apache Pulsar has specific
  failure archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed Apache Pulsar traffic
  before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the Apache Pulsar service. Every
context listed below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="pulsar" (returns every pulsar.* context Netdata sees)
2. query_metrics with contexts=[pulsar.messages_rate, pulsar.throughput_rate, pulsar.storage_operations_rate, pulsar.subscription_msg_rate_redeliver, pulsar.replication_rate, pulsar.replication_throughput_rate] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="pulsar.*"
```

Load-bearing contexts for this service:

- `pulsar.messages_rate`: Messages Rate (messages/s). Dimensions: publish, dispatch.
- `pulsar.throughput_rate`: Throughput Rate (KiB/s). Dimensions: publish, dispatch.
- `pulsar.storage_operations_rate`: Storage Read/Write Operations Rate (message batches/s).
                                    Dimensions: read, write.
- `pulsar.subscription_msg_rate_redeliver`: Subscriptions Redelivered Message Rate (messages/s).
                                            Dimensions: redelivered.
- `pulsar.replication_rate`: Replication Rate (messages/s). Dimensions: in, out.
- `pulsar.replication_throughput_rate`: Replication Throughput Rate (KiB/s). Dimensions: in, out.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for Apache Pulsar:

- Host-resource pressure masquerading as application bug.
- Dependent service (DB, cache, upstream) causing a secondary symptom in the instrumented service.
- Configuration change that was never reloaded (some subsystems only pick up config on full
  restart).

Escalate by widening the query window: 2-6 hours instead of 15 minutes. Slow-moving causes are
invisible at triage window sizes.

## References

- [`rules/availability.md`](./rules/availability.md)
- [`rules/latency.md`](./rules/latency.md)
- [`rules/saturation-resource-utilization.md`](./rules/saturation-resource-utilization.md)
- [`rules/backlog-consumer-health.md`](./rules/backlog-consumer-health.md)
- [`rules/replication-consistency.md`](./rules/replication-consistency.md)
- [`rules/resource-pressure.md`](./rules/resource-pressure.md)
- [`rules/internal-state.md`](./rules/internal-state.md)
- [`rules/errors.md`](./rules/errors.md)
- [`rules/bookkeeper-storage-internals.md`](./rules/bookkeeper-storage-internals.md)
- Netdata operator playbook: the authoritative source material this skill summarizes.
- `skills/netdata-mcp-integration/` for the transport setup.
- `skills/netdata-otel-setup/` if additional application signals are needed beyond what Netdata
  collects natively.
