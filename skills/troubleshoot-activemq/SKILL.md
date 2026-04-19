---
name: troubleshoot-activemq
description: "Use when diagnosing issues with Apache ActiveMQ Classic 5.x: memory pressure cascade, store exhaustion spiral, gc pause death spiral, poison message / dlq storm, or connection/thread exhaustion. Queries Netdata via MCP for Apache ActiveMQ Classic 5.x health signals, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - activemq
---

# Troubleshoot Apache ActiveMQ Classic 5.x

## When to use this skill

- **Memory pressure cascade**: Slow consumers or high producer rate then destination memory limit
                               reached then producer flow control activates then producers block
                               silently then upstream services hang then cascading failures. This is
                               the #1 operational failure pattern.
- **Store exhaustion spiral**: Consumers lag producers, or DLQ accumulates uncollected poison
                               messages then journal files grow then disk fills then broker rejects
                               persistent messages then total service loss. Often a slow burn over
                               days/weeks.
- **GC pause death spiral**: JVM heap pressure then long GC pauses then client heartbeat timeouts
                             then mass disconnection then reconnection storm then more heap pressure
                             then longer GC pauses then repeat.
- **Poison message / DLQ storm**: Messages that cannot be processed then redelivery up to max
                                  retries then land in DLQ then DLQ grows indefinitely (no TTL by
                                  default) then silent storage leak and correctness loss.
- **Connection/thread exhaustion**: Many short-lived or leaked connections then thread pool or FD
                                    exhaustion then broker unresponsive to all clients.
- **KahaDB corruption**: Unclean shutdown with writes in flight then journal or index corruption
                         then broker refuses to start or loses messages.
- Any time the user reports a Apache ActiveMQ Classic 5.x service behaving outside its expected
  envelope (elevated errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a Apache ActiveMQ Classic 5.x instance
  and wants a structured triage path.

## Key facts

- This skill wraps the Netdata operator playbook for Apache ActiveMQ Classic 5.x. It does not
  replace the playbook; it routes a coding agent through MCP queries against the same signals the
  playbook relies on.
- Dominant failure archetypes the playbook calls out: Memory pressure cascade; Store exhaustion
  spiral; GC pause death spiral; Poison message / DLQ storm; Connection/thread exhaustion.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your Apache ActiveMQ Classic 5.x instrumentation adds. Both
  paths end at the same MCP query surface.
- Netdata's activemq collector emits 3 context(s) under `activemq.*`. The rule files enumerate which
  contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the Apache ActiveMQ Classic 5.x service is up. Query Netdata via MCP with `list_nodes`
   and filter by the host running the target. A missing node means the symptom is at the network or
   orchestrator layer, not inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **Memory pressure cascade**. Slow consumers or high producer rate then destination
   memory limit reached then producer flow control activates then producers block silently then
   upstream services hang then cascading failures. This is the #1 operational failure pattern.
   Inspect the rule file whose signals move first for this mode.
4. Check for **Store exhaustion spiral**. Consumers lag producers, or DLQ accumulates uncollected
   poison messages then journal files grow then disk fills then broker rejects persistent messages
   then total service loss. Often a slow burn over days/weeks. Inspect the rule file whose signals
   move first for this mode.
5. Check for **GC pause death spiral**. JVM heap pressure then long GC pauses then client heartbeat
   timeouts then mass disconnection then reconnection storm then more heap pressure then longer GC
   pauses then repeat. Inspect the rule file whose signals move first for this mode.
6. Check for **Poison message / DLQ storm**. Messages that cannot be processed then redelivery up to
   max retries then land in DLQ then DLQ grows indefinitely (no TTL by default) then silent storage
   leak and correctness loss. Inspect the rule file whose signals move first for this mode.
7. Check for **Connection/thread exhaustion**. Many short-lived or leaked connections then thread
   pool or FD exhaustion then broker unresponsive to all clients. Inspect the rule file whose
   signals move first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from Apache ActiveMQ Classic 5.x
list_metrics with q="activemq"

# Pull a specific context over the last window
query_metrics with context="activemq.unprocessed_messages", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="activemq.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating Apache ActiveMQ Classic 5.x as a generic HTTP or process health check. Apache ActiveMQ
  Classic 5.x has specific failure archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed Apache ActiveMQ
  Classic 5.x traffic before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the Apache ActiveMQ Classic 5.x
service. Every context listed below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="activemq" (returns every activemq.* context Netdata sees)
2. query_metrics with contexts=[activemq.unprocessed_messages, activemq.messages, activemq.consumers] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="activemq.*"
```

Load-bearing contexts for this service:

- `activemq.unprocessed_messages`: Unprocessed Messages (messages). Dimensions: unprocessed.
- `activemq.messages`: Messaged (messages/s). Dimensions: enqueued, dequeued.
- `activemq.consumers`: Consumers (consumers). Dimensions: consumers.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for Apache ActiveMQ Classic 5.x:

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
