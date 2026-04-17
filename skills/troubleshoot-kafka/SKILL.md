---
name: troubleshoot-kafka
description: "Use when diagnosing issues with Kafka: \"the isr shrinks\", \"the partition goes leaderless\", \"the consumer falls behind\", \"the controller is overwhelmed\", or \"the broker runs out of disk\". Queries Netdata via MCP for Kafka health signals, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - kafka
---

# Troubleshoot Kafka

## When to use this skill

- **"The ISR shrinks"**: A follower can't keep up (slow disk, network issue, GC pause). ISR shrinks
                         then if enough followers leave, `min.insync.replicas` (default 1) can't be
                         satisfied then producers with `acks=all` get `NotEnoughReplicasException`.
                         Most common degradation mode.
- **"The partition goes leaderless"**: Leader dies and no ISR member is available. If
                                       `unclean.leader.election.enable=false` (default since Kafka
                                       0.11.0.0), the partition is completely unavailable. If
                                       enabled, a behind follower takes over and data is silently
                                       lost.
- **"The consumer falls behind"**: Consumer lag grows because consumers are slow, rebalancing, or
                                   dead. Eventually the consumer's offset points to data deleted by
                                   retention then `OffsetOutOfRangeException` then data loss from
                                   the consumer's perspective.
- **"The controller is overwhelmed"**: Too many partitions, broker joins/leaves, or ISR changes. The
                                       controller's event queue backs up. Metadata propagation
                                       stalls. Requests fail with `NOT_LEADER_FOR_PARTITION`.
- **"The broker runs out of disk"**: Kafka shuts down the log directory. No graceful degradation.
                                     Partitions on that directory become unavailable.
- **"The request queue fills up"**: Network threads accept requests faster than I/O threads process
                                    them. Queue fills, network threads block, clients time out and
                                    retry, adding more load (positive feedback loop).
- Any time the user reports a Kafka service behaving outside its expected envelope (elevated errors,
  latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a Kafka instance and wants a structured
  triage path.

## Key facts

- This skill wraps the Netdata operator playbook for Kafka. It does not replace the playbook; it
  routes a coding agent through MCP queries against the same signals the playbook relies on.
- Dominant failure archetypes the playbook calls out: "The ISR shrinks"; "The partition goes
  leaderless"; "The consumer falls behind"; "The controller is overwhelmed"; "The broker runs out of
  disk".
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your Kafka instrumentation adds. Both paths end at the same MCP
  query surface.

## Step-by-step

1. Confirm the Kafka service is up. Query Netdata via MCP with `list_nodes` and filter by the host
   running the target. A missing node means the symptom is at the network or orchestrator layer, not
   inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **"The ISR shrinks"**. A follower can't keep up (slow disk, network issue, GC pause).
   ISR shrinks then if enough followers leave, `min.insync.replicas` (default 1) can't be satisfied
   then producers with `acks=all` get `NotEnoughReplicasException`. Most common degradation mode.
   Inspect the rule file whose signals move first for this mode.
4. Check for **"The partition goes leaderless"**. Leader dies and no ISR member is available. If
   `unclean.leader.election.enable=false` (default since Kafka 0.11.0.0), the partition is
   completely unavailable. If enabled, a behind follower takes over and data is silently lost.
   Inspect the rule file whose signals move first for this mode.
5. Check for **"The consumer falls behind"**. Consumer lag grows because consumers are slow,
   rebalancing, or dead. Eventually the consumer's offset points to data deleted by retention then
   `OffsetOutOfRangeException` then data loss from the consumer's perspective. Inspect the rule file
   whose signals move first for this mode.
6. Check for **"The controller is overwhelmed"**. Too many partitions, broker joins/leaves, or ISR
   changes. The controller's event queue backs up. Metadata propagation stalls. Requests fail with
   `NOT_LEADER_FOR_PARTITION`. Inspect the rule file whose signals move first for this mode.
7. Check for **"The broker runs out of disk"**. Kafka shuts down the log directory. No graceful
   degradation. Partitions on that directory become unavailable. Inspect the rule file whose signals
   move first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from Kafka
list_metrics with optional filter by context prefix

# Pull a specific signal over the last window
query_metrics with context=<signal>, relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with host=<host> or service=<service>

# Correlate a known problem signal with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating Kafka as a generic HTTP or process health check. Kafka has specific failure archetypes
  (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed Kafka traffic before
  escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the Kafka service:

```text
1. list_metrics filtered by the Kafka service's context prefix.
2. query_metrics for the key signals from the first-triggered domain over the last 30 minutes.
3. find_anomalous_metrics scoped to the same service/time window.
```

Signals the playbook considers load-bearing:

  - the specific signals listed in the domain rule files

A clean result means every key signal is within its expected band and the `find_anomalous_metrics`
list is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for Kafka:

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
