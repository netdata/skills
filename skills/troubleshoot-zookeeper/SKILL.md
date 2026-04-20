---
name: troubleshoot-zookeeper
description: "Use when diagnosing issues with Apache ZooKeeper: quorum loss, write pipeline stall, gc pause cascade, session expiration storm, or heap exhaustion / oom. Queries Netdata via MCP for server state (role), service liveness, request latency (aggregated), write latency (update latency), outstanding requests (queue depth), applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - zookeeper
---

# Troubleshoot Apache ZooKeeper

## When to use this skill

- **Quorum Loss**: Network partition or >50% node failure prevents writes. The
- **Write Pipeline Stall**: Transaction log disk saturation (fsync latency spikes).
- **GC Pause Cascade**: JVM Stop-the-World GC freezes the process. Clients miss
- **Session Expiration Storm**: Leader failover or network event causes mass session
- **Heap Exhaustion / OOM**: Cumulative znode growth, unbounded watches, or session
- **Snapshot/Recovery Stall**: Large DataTree makes snapshot creation CPU-intensive
- Any time the user reports a Apache ZooKeeper service behaving outside its expected envelope
  (elevated errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a Apache ZooKeeper instance and wants a
  structured triage path.

## Key facts

- This skill wraps the Netdata operator playbook for Apache ZooKeeper. It does not replace the
  playbook; it routes a coding agent through MCP queries against the same signals the playbook
  relies on.
- ZooKeeper is a distributed coordination service built on a replicated state machine. It maintains
  a hierarchical namespace of data nodes (znodes) entirely in memory and replicates every mutation
  across an ensemble of servers using the ZAB (ZooKeeper Atomic Broadcast) protocol.
- The playbook decomposes Apache ZooKeeper health into 9 signal domains: Availability, Latency,
  Throughput, Connections & Sessions, Replication & Sync, Data Tree & Memory. Each domain maps to
  one rule file in this skill.
- Dominant failure archetypes the playbook calls out: Quorum Loss; Write Pipeline Stall; GC Pause
  Cascade; Session Expiration Storm; Heap Exhaustion / OOM.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your Apache ZooKeeper instrumentation adds. Both paths end at
  the same MCP query surface.
- Netdata's zookeeper collector emits 17 context(s) under `zookeeper.*`. The rule files enumerate
  which contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the Apache ZooKeeper service is up. Query Netdata via MCP with `list_nodes` and filter by
   the host running the target. A missing node means the symptom is at the network or orchestrator
   layer, not inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **Quorum Loss**. Network partition or >50% node failure prevents writes. The Inspect
   the rule file whose signals move first for this mode.
4. Check for **Write Pipeline Stall**. Transaction log disk saturation (fsync latency spikes).
   Inspect the rule file whose signals move first for this mode.
5. Check for **GC Pause Cascade**. JVM Stop-the-World GC freezes the process. Clients miss Inspect
   the rule file whose signals move first for this mode.
6. Check for **Session Expiration Storm**. Leader failover or network event causes mass session
   Inspect the rule file whose signals move first for this mode.
7. Check for **Heap Exhaustion / OOM**. Cumulative znode growth, unbounded watches, or session
   Inspect the rule file whose signals move first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from Apache ZooKeeper
list_metrics with q="zookeeper"

# Pull a specific context over the last window
query_metrics with context="zookeeper.connections", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="zookeeper.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating Apache ZooKeeper as a generic HTTP or process health check. Apache ZooKeeper has specific
  failure archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed Apache ZooKeeper
  traffic before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the Apache ZooKeeper service. Every
context listed below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="zookeeper" (returns every zookeeper.* context Netdata sees)
2. query_metrics with contexts=[zookeeper.connections, zookeeper.connections_dropped, zookeeper.connections_rejected, zookeeper.uptime, zookeeper.stale_requests_dropped, zookeeper.auth_fails] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="zookeeper.*"
```

Load-bearing contexts for this service:

- `zookeeper.connections`: Alive Connections (connections). Dimensions: alive.
- `zookeeper.connections_dropped`: Dropped Connections (connections/s). Dimensions: dropped.
- `zookeeper.connections_rejected`: Rejected Connections (connections/s). Dimensions: rejected.
- `zookeeper.uptime`: Uptime (seconds). Dimensions: uptime.
- `zookeeper.stale_requests_dropped`: Stale Requests Dropped (requests/s). Dimensions: dropped.
- `zookeeper.auth_fails`: Auth Fails (fails/s). Dimensions: auth.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for Apache ZooKeeper:

- Host-resource pressure masquerading as application bug.
- Dependent service (DB, cache, upstream) causing a secondary symptom in the instrumented service.
- Configuration change that was never reloaded (some subsystems only pick up config on full
  restart).

Escalate by widening the query window: 2-6 hours instead of 15 minutes. Slow-moving causes are
invisible at triage window sizes.

## References

- [`rules/availability.md`](./rules/availability.md)
- [`rules/latency.md`](./rules/latency.md)
- [`rules/throughput.md`](./rules/throughput.md)
- [`rules/connections-sessions.md`](./rules/connections-sessions.md)
- [`rules/replication-sync.md`](./rules/replication-sync.md)
- [`rules/data-tree-memory.md`](./rules/data-tree-memory.md)
- [`rules/errors-integrity.md`](./rules/errors-integrity.md)
- [`rules/jvm-resource-utilization.md`](./rules/jvm-resource-utilization.md)
- [`rules/security.md`](./rules/security.md)
- Netdata operator playbook: the authoritative source material this skill summarizes.
- `skills/netdata-mcp-integration/` for the transport setup.
- `skills/netdata-otel-setup/` if additional application signals are needed beyond what Netdata
  collects natively.
