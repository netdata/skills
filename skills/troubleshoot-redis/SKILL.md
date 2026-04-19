---
name: troubleshoot-redis
description: "Use when diagnosing issues with Redis: the fork/cow storm, the event loop wedge, the replication backlog overflow, the memory pressure spiral, or the connection exhaustion cascade. Queries Netdata via MCP for redis reachability, uptime and unexpected restarts, memory usage ratio, memory fragmentation ratio, rejected connections, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - redis
---

# Troubleshoot Redis

## When to use this skill

- **The Fork/COW Storm**: Persistence fork causes memory to double via copy-on-write. OOM kill or
                          massive latency spike.
- **The Event Loop Wedge**: A single slow command (KEYS *, large SORT, Lua script) blocks all other
                            clients.
- **The Replication Backlog Overflow**: Replica falls behind, backlog wraps, full resync triggered;
                                        which triggers another fork.
- **The Memory Pressure Spiral**: Eviction starts, evicted keys are re-requested, cache miss
                                  triggers re-population write which evicts more keys.
- **The Connection Exhaustion Cascade**: maxclients hit, new connections rejected, applications
                                         retry aggressively, making it worse.
- Any time the user reports a Redis service behaving outside its expected envelope (elevated errors,
  latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a Redis instance and wants a structured
  triage path.

## Key facts

- This skill wraps the Netdata operator playbook for Redis. It does not replace the playbook; it
  routes a coding agent through MCP queries against the same signals the playbook relies on.
- Redis is a single-threaded event loop processing commands against in-memory data structures, with
  optional persistence to disk and optional replication to replicas.
- The playbook decomposes Redis health into 14 signal domains: Liveness & State, Memory,
  Connections, Throughput & Latency, Persistence, Replication. Each domain maps to one rule file in
  this skill.
- Dominant failure archetypes the playbook calls out: The Fork/COW Storm; The Event Loop Wedge; The
  Replication Backlog Overflow; The Memory Pressure Spiral; The Connection Exhaustion Cascade.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your Redis instrumentation adds. Both paths end at the same MCP
  query surface.
- Netdata's redis collector emits 25 context(s) under `redis.*`. The rule files enumerate which
  contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the Redis service is up. Query Netdata via MCP with `list_nodes` and filter by the host
   running the target. A missing node means the symptom is at the network or orchestrator layer, not
   inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **The Fork/COW Storm**. Persistence fork causes memory to double via copy-on-write. OOM
   kill or massive latency spike. Inspect the rule file whose signals move first for this mode.
4. Check for **The Event Loop Wedge**. A single slow command (KEYS *, large SORT, Lua script) blocks
   all other clients. Inspect the rule file whose signals move first for this mode.
5. Check for **The Replication Backlog Overflow**. Replica falls behind, backlog wraps, full resync
   triggered; which triggers another fork. Inspect the rule file whose signals move first for this
   mode.
6. Check for **The Memory Pressure Spiral**. Eviction starts, evicted keys are re-requested, cache
   miss triggers re-population write which evicts more keys. Inspect the rule file whose signals
   move first for this mode.
7. Check for **The Connection Exhaustion Cascade**. maxclients hit, new connections rejected,
   applications retry aggressively, making it worse. Inspect the rule file whose signals move first
   for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from Redis
list_metrics with q="redis"

# Pull a specific context over the last window
query_metrics with context="redis.connections", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="redis.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating Redis as a generic HTTP or process health check. Redis has specific failure archetypes
  (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed Redis traffic before
  escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the Redis service. Every context listed
below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="redis" (returns every redis.* context Netdata sees)
2. query_metrics with contexts=[redis.connections, redis.clients, redis.ping_latency, redis.keyspace_lookup_hit_rate, redis.bgsave_health, redis.connected_replicas] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="redis.*"
```

Load-bearing contexts for this service:

- `redis.connections`: Accepted and rejected (maxclients limit) connections (connections/s).
                       Dimensions: accepted, rejected.
- `redis.clients`: Clients (clients). Dimensions: connected, blocked, tracking, in_timeout_table.
- `redis.ping_latency`: Ping latency (seconds). Dimensions: min, max, avg.
- `redis.keyspace_lookup_hit_rate`: Keys lookup hit rate (percentage). Dimensions: lookup_hit_rate.
- `redis.bgsave_health`: Status of the last RDB save operation (0: ok, 1: err) (status). Dimensions:
                         last_bgsave.
- `redis.connected_replicas`: Connected replicas (replicas). Dimensions: connected.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for Redis:

- Host-resource pressure masquerading as application bug.
- Dependent service (DB, cache, upstream) causing a secondary symptom in the instrumented service.
- Configuration change that was never reloaded (some subsystems only pick up config on full
  restart).

Escalate by widening the query window: 2-6 hours instead of 15 minutes. Slow-moving causes are
invisible at triage window sizes.

## References

- [`rules/liveness-state.md`](./rules/liveness-state.md)
- [`rules/memory.md`](./rules/memory.md)
- [`rules/connections.md`](./rules/connections.md)
- [`rules/throughput-latency.md`](./rules/throughput-latency.md)
- [`rules/persistence.md`](./rules/persistence.md)
- [`rules/replication.md`](./rules/replication.md)
- [`rules/persistence-health.md`](./rules/persistence-health.md)
- [`rules/cluster-redis-cluster-mode-only.md`](./rules/cluster-redis-cluster-mode-only.md)
- [`rules/cpu-processing.md`](./rules/cpu-processing.md)
- [`rules/key-expiration.md`](./rules/key-expiration.md)
- [`rules/network.md`](./rules/network.md)
- [`rules/security-integrity.md`](./rules/security-integrity.md)
- [`rules/pubsub-and-streams.md`](./rules/pubsub-and-streams.md)
- [`rules/active-defragmentation-redis-40.md`](./rules/active-defragmentation-redis-40.md)
- Netdata operator playbook: the authoritative source material this skill summarizes.
- `skills/netdata-mcp-integration/` for the transport setup.
- `skills/netdata-otel-setup/` if additional application signals are needed beyond what Netdata
  collects natively.
