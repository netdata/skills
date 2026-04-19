---
name: troubleshoot-nats
description: "Use when diagnosing issues with NATS: slow consumer cascade, file descriptor exhaustion, jetstream raft instability, memory pressure / oom, or silent message loss (core nats). Queries Netdata via MCP for NATS health signals, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - nats
---

# Troubleshoot NATS

## When to use this skill

- **Slow consumer cascade**: A subscriber falls behind then server disconnects it then
- **File descriptor exhaustion**: Connection count hits OS `ulimit -n`. No new
- **JetStream Raft instability**: Network latency or GC pauses cause Raft
- **Memory pressure / OOM**: Slow consumers buffering in memory, large subscription
- **Silent message loss (core NATS)**: Publisher sends to subject with zero
- Any time the user reports a NATS service behaving outside its expected envelope (elevated errors,
  latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a NATS instance and wants a structured
  triage path.

## Key facts

- This skill wraps the Netdata operator playbook for NATS. It does not replace the playbook; it
  routes a coding agent through MCP queries against the same signals the playbook relies on.
- NATS is a subject-based message router written in Go. At its core, the server maintains an
  in-memory **subject tree** (trie) mapping subject strings to sets of subscriptions. Every inbound
  message is matched against this tree and fanned out to all matching subscribers. There is no
  intermediate queue in core NATS; messages flow through the routing engine in real-time.
- Dominant failure archetypes the playbook calls out: Slow consumer cascade; File descriptor
  exhaustion; JetStream Raft instability; Memory pressure / OOM; Silent message loss (core NATS).
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your NATS instrumentation adds. Both paths end at the same MCP
  query surface.
- Netdata's nats collector emits 40 context(s) under `nats.*`. The rule files enumerate which
  contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the NATS service is up. Query Netdata via MCP with `list_nodes` and filter by the host
   running the target. A missing node means the symptom is at the network or orchestrator layer, not
   inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **Slow consumer cascade**. A subscriber falls behind then server disconnects it then
   Inspect the rule file whose signals move first for this mode.
4. Check for **File descriptor exhaustion**. Connection count hits OS `ulimit -n`. No new Inspect
   the rule file whose signals move first for this mode.
5. Check for **JetStream Raft instability**. Network latency or GC pauses cause Raft Inspect the
   rule file whose signals move first for this mode.
6. Check for **Memory pressure / OOM**. Slow consumers buffering in memory, large subscription
   Inspect the rule file whose signals move first for this mode.
7. Check for **Silent message loss (core NATS)**. Publisher sends to subject with zero Inspect the
   rule file whose signals move first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from NATS
list_metrics with q="nats"

# Pull a specific context over the last window
query_metrics with context="nats.server_connections", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="nats.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating NATS as a generic HTTP or process health check. NATS has specific failure archetypes (see
  Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed NATS traffic before
  escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the NATS service. Every context listed
below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="nats" (returns every nats.* context Netdata sees)
2. query_metrics with contexts=[nats.server_connections, nats.server_connections_rate, nats.server_health_probe_status, nats.server_uptime, nats.account_connections, nats.account_connections_rate] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="nats.*"
```

Load-bearing contexts for this service:

- `nats.server_connections`: Server Active Connections (connections). Dimensions: active.
- `nats.server_connections_rate`: Server Connections (connections/s). Dimensions: connections.
- `nats.server_health_probe_status`: Server Health Probe Status (status). Dimensions: ok, error.
- `nats.server_uptime`: Server Uptime (seconds). Dimensions: uptime.
- `nats.account_connections`: Account Active Connections (connections). Dimensions: active.
- `nats.account_connections_rate`: Account Connections (connections/s). Dimensions: connections.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for NATS:

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
