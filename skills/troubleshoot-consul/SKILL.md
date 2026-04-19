---
name: troubleshoot-consul
description: "Use when diagnosing issues with Consul: leader instability, gossip partition / flapping, catalog bloat / memory exhaustion, blocking query accumulation, or certificate/ca failures. Queries Netdata via MCP for Consul health signals, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - consul
---

# Troubleshoot Consul

## When to use this skill

- **Leader instability**: The leader cannot commit Raft entries fast enough (disk latency, CPU
                          starvation, network partitions). Repeated elections. All writes fail
                          during elections. Cascading effect: anti-entropy cannot sync, health
                          checks go stale, service discovery returns stale data.
- **Gossip partition / flapping**: Network issues cause nodes to oscillate between alive/failed/left
                                   states. This creates a storm of catalog deregistrations and
                                   re-registrations. Health checks flip. Downstream consumers (load
                                   balancers, service meshes) react to every flip, causing traffic
                                   storms.
- **Catalog bloat / memory exhaustion**: Large numbers of registered services, checks, or KV entries
                                         grow unbounded. Snapshots become enormous. Raft replication
                                         slows. Server restarts take minutes to hours to restore the
                                         snapshot.
- **Blocking query accumulation**: Consul's watch mechanism uses HTTP long-polling (blocking
                                   queries). Each blocking query holds a goroutine and a connection.
                                   Misconfigured or leaked watches accumulate indefinitely. Servers
                                   eventually run out of goroutines or file descriptors.
- **Certificate/CA failures**: Connect certificates expire without rotation. CA root rotation fails
                               mid-roll. Envoy sidecars reject connections. Silent mutual TLS
                               failures cause intermittent service-to-service communication failures
                               that look like application bugs.
- **Cross-DC WAN degradation**: WAN gossip between datacenters degrades silently. Cross-DC service
                                lookups fail or return stale results. Prepared queries that failover
                                across DCs stop working.
- Any time the user reports a Consul service behaving outside its expected envelope (elevated
  errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a Consul instance and wants a structured
  triage path.

## Key facts

- This skill wraps the Netdata operator playbook for Consul. It does not replace the playbook; it
  routes a coding agent through MCP queries against the same signals the playbook relies on.
- Consul is a distributed system built on three foundational subsystems that operate concurrently:
  **Raft consensus**, **Serf gossip**, and a **catalog/state machine**. Understanding how these
  interact is the single most important thing for an operator.
- Dominant failure archetypes the playbook calls out: Leader instability; Gossip partition /
  flapping; Catalog bloat / memory exhaustion; Blocking query accumulation; Certificate/CA failures.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your Consul instrumentation adds. Both paths end at the same
  MCP query surface.
- Netdata's consul collector emits 35 context(s) under `consul.*`. The rule files enumerate which
  contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the Consul service is up. Query Netdata via MCP with `list_nodes` and filter by the host
   running the target. A missing node means the symptom is at the network or orchestrator layer, not
   inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **Leader instability**. The leader cannot commit Raft entries fast enough (disk
   latency, CPU starvation, network partitions). Repeated elections. All writes fail during
   elections. Cascading effect: anti-entropy cannot sync, health checks go stale, service discovery
   returns stale data. Inspect the rule file whose signals move first for this mode.
4. Check for **Gossip partition / flapping**. Network issues cause nodes to oscillate between
   alive/failed/left states. This creates a storm of catalog deregistrations and re-registrations.
   Health checks flip. Downstream consumers (load balancers, service meshes) react to every flip,
   causing traffic storms. Inspect the rule file whose signals move first for this mode.
5. Check for **Catalog bloat / memory exhaustion**. Large numbers of registered services, checks, or
   KV entries grow unbounded. Snapshots become enormous. Raft replication slows. Server restarts
   take minutes to hours to restore the snapshot. Inspect the rule file whose signals move first for
   this mode.
6. Check for **Blocking query accumulation**. Consul's watch mechanism uses HTTP long-polling
   (blocking queries). Each blocking query holds a goroutine and a connection. Misconfigured or
   leaked watches accumulate indefinitely. Servers eventually run out of goroutines or file
   descriptors. Inspect the rule file whose signals move first for this mode.
7. Check for **Certificate/CA failures**. Connect certificates expire without rotation. CA root
   rotation fails mid-roll. Envoy sidecars reject connections. Silent mutual TLS failures cause
   intermittent service-to-service communication failures that look like application bugs. Inspect
   the rule file whose signals move first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from Consul
list_metrics with q="consul"

# Pull a specific context over the last window
query_metrics with context="consul.autopilot_health_status", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="consul.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating Consul as a generic HTTP or process health check. Consul has specific failure archetypes
  (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed Consul traffic before
  escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the Consul service. Every context
listed below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="consul" (returns every consul.* context Netdata sees)
2. query_metrics with contexts=[consul.autopilot_health_status, consul.autopilot_server_health_status, consul.autopilot_server_serf_status, consul.autopilot_server_voter_status, consul.server_leadership_status, consul.node_health_check_status] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="consul.*"
```

Load-bearing contexts for this service:

- `consul.autopilot_health_status`: Autopilot cluster health status (status). Dimensions: healthy,
                                    unhealthy.
- `consul.autopilot_server_health_status`: Autopilot server health status (status). Dimensions:
                                           healthy, unhealthy.
- `consul.autopilot_server_serf_status`: Autopilot server Serf status (status). Dimensions: active,
                                         failed, left, none.
- `consul.autopilot_server_voter_status`: Autopilot server Raft voting membership (status).
                                          Dimensions: voter, not_voter.
- `consul.server_leadership_status`: Server leadership status (status). Dimensions: leader,
                                     not_leader.
- `consul.node_health_check_status`: Node health check status (status). Dimensions: passing,
                                     maintenance, warning, critical.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for Consul:

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
