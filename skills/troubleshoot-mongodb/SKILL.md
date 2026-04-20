---
name: troubleshoot-mongodb
description: "Use when diagnosing issues with MongoDB: cache pressure cascade, oplog window collapse, connection storm spiral, checkpoint stall write freeze, or silent index regression. Queries Netdata via MCP for MongoDB health signals, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - mongodb
---

# Troubleshoot MongoDB

## When to use this skill

- **Cache pressure cascade**: Cache fills then background eviction fails then application threads
                              evict then latency spikes then connections pile up then ticket
                              exhaustion then everything queues then reconnection storms then
                              self-reinforcing degradation.
- **Oplog window collapse**: Write volume spikes then oplog fills faster then window shrinks then
                             secondary falls behind then secondary can't catch up before window
                             closes then enters RECOVERING then requires full initial sync then
                             remaining nodes absorb more load then risk of more secondaries falling
                             beh...
- **Connection storm spiral**: A triggering event (election, deploy, network blip) causes mass
                               reconnection then thread creation overhead then memory spike then
                               ticket contention then existing queries slow then more timeouts then
                               more reconnections then positive feedback loop.
- **Checkpoint stall write freeze**: Dirty data accumulates then checkpoint falls behind then
                                     journal fills then WiredTiger blocks ALL new writes then
                                     complete write freeze while reads may still work from cache.
- **Silent index regression**: Index dropped or planner changes plan then queries silently switch to
                               collection scans then latency increases gradually proportional to
                               collection growth then eventually overwhelms I/O.
- **Election storm**: Primary becomes unreachable then election then winner unstable then repeated
                      elections then each causes 2-12 second write outage then cluster oscillates.
- Any time the user reports a MongoDB service behaving outside its expected envelope (elevated
  errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a MongoDB instance and wants a structured
  triage path.

## Key facts

- This skill wraps the Netdata operator playbook for MongoDB. It does not replace the playbook; it
  routes a coding agent through MCP queries against the same signals the playbook relies on.
- MongoDB is a document-oriented database built on interconnected subsystems that an operator must
  understand to reason about failures effectively.
- Dominant failure archetypes the playbook calls out: Cache pressure cascade; Oplog window collapse;
  Connection storm spiral; Checkpoint stall write freeze; Silent index regression.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your MongoDB instrumentation adds. Both paths end at the same
  MCP query surface.
- Netdata's mongodb collector emits 53 context(s) under `mongodb.*`. The rule files enumerate which
  contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the MongoDB service is up. Query Netdata via MCP with `list_nodes` and filter by the host
   running the target. A missing node means the symptom is at the network or orchestrator layer, not
   inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **Cache pressure cascade**. Cache fills then background eviction fails then application
   threads evict then latency spikes then connections pile up then ticket exhaustion then everything
   queues then reconnection storms then self-reinforcing degradation. Inspect the rule file whose
   signals move first for this mode.
4. Check for **Oplog window collapse**. Write volume spikes then oplog fills faster then window
   shrinks then secondary falls behind then secondary can't catch up before window closes then
   enters RECOVERING then requires full initial sync then remaining nodes absorb more load then risk
   of more secondaries falling behind. Inspect the rule file whose signals move first for this mode.
5. Check for **Connection storm spiral**. A triggering event (election, deploy, network blip) causes
   mass reconnection then thread creation overhead then memory spike then ticket contention then
   existing queries slow then more timeouts then more reconnections then positive feedback loop.
   Inspect the rule file whose signals move first for this mode.
6. Check for **Checkpoint stall write freeze**. Dirty data accumulates then checkpoint falls behind
   then journal fills then WiredTiger blocks ALL new writes then complete write freeze while reads
   may still work from cache. Inspect the rule file whose signals move first for this mode.
7. Check for **Silent index regression**. Index dropped or planner changes plan then queries
   silently switch to collection scans then latency increases gradually proportional to collection
   growth then eventually overwhelms I/O. Inspect the rule file whose signals move first for this
   mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from MongoDB
list_metrics with q="mongodb"

# Pull a specific context over the last window
query_metrics with context="mongodb.operations_by_type_rate", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="mongodb.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating MongoDB as a generic HTTP or process health check. MongoDB has specific failure
  archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed MongoDB traffic
  before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the MongoDB service. Every context
listed below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="mongodb" (returns every mongodb.* context Netdata sees)
2. query_metrics with contexts=[mongodb.operations_by_type_rate, mongodb.document_operations_rate, mongodb.active_clients_count, mongodb.connections_usage, mongodb.connections_by_state_count, mongodb.connections_rate] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="mongodb.*"
```

Load-bearing contexts for this service:

- `mongodb.operations_by_type_rate`: Operations by type (operations/s). Dimensions: insert, query,
                                     update, delete, getmore, command.
- `mongodb.document_operations_rate`: Document operations (operations/s). Dimensions: inserted,
                                      deleted, returned, updated.
- `mongodb.active_clients_count`: Connected clients (clients). Dimensions: readers, writers.
- `mongodb.connections_usage`: Connections usage (connections). Dimensions: available, used.
- `mongodb.connections_by_state_count`: Connections By State (connections). Dimensions: active,
                                        threaded, exhaust_is_master, exhaust_hello,
                                        awaiting_topology_changes.
- `mongodb.connections_rate`: Connections Rate (connections/s). Dimensions: created.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for MongoDB:

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
