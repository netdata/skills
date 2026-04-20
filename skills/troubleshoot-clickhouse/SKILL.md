---
name: troubleshoot-clickhouse
description: "Use when diagnosing issues with ClickHouse: merge debt spiral, memory exhaustion, replication lag cascade, zookeeper/keeper saturation, or disk space collapse. Queries Netdata via MCP for server process liveness, replicated table read/write availability, active part count per table, merge activity and progress, insert delays and rejections, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - clickhouse
---

# Troubleshoot ClickHouse

## When to use this skill

- **Merge Debt Spiral**: Inserts arrive faster than merges complete then part count grows then merge
                         cost increases (more parts to combine) then merges fall further behind then
                         eventually "too many parts" rejections halt writes.
- **Memory Exhaustion**: Single large query with expansive GROUP BY or JOIN then OOM kill or query
                         cancellation then cascading retries compound the problem.
- **Replication Lag Cascade**: Network partition or ZK issues then replica falls behind then
                               catch-up requires fetching many parts then disk/network saturation
                               slows catch-up further.
- **ZooKeeper/Keeper Saturation**: Too many tables, excessive DDL, or ZK disk bottleneck then
                                   coordination latency spikes then session timeouts then replicas
                                   become read-only then cluster-wide write failure.
- **Disk Space Collapse**: Merges need free space to write merged parts before deleting originals.
                           Disk at 85-90% then merges cannot complete then small parts pile up
                           consuming more metadata space then death spiral.
- **Silent Mutation Blocking**: Heavy ALTER UPDATE/DELETE runs then mutation pool saturated then
                                mutations and merges share coordination then merges blocked silently
                                then part count grows while the system appears "busy."
- Any time the user reports a ClickHouse service behaving outside its expected envelope (elevated
  errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a ClickHouse instance and wants a
  structured triage path.

## Key facts

- This skill wraps the Netdata operator playbook for ClickHouse. It does not replace the playbook;
  it routes a coding agent through MCP queries against the same signals the playbook relies on.
- ClickHouse is a column-oriented OLAP database optimized for analytical queries on large datasets.
  Understanding its internal machinery is essential because its failure modes are distinctive; it
  does not fail like a transactional database.
- The playbook decomposes ClickHouse health into 11 signal domains: Availability, Internal State;
  Parts And Merges, Insert Health, Memory, Errors, Disk. Each domain maps to one rule file in this
  skill.
- Dominant failure archetypes the playbook calls out: Merge Debt Spiral; Memory Exhaustion;
  Replication Lag Cascade; ZooKeeper/Keeper Saturation; Disk Space Collapse.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your ClickHouse instrumentation adds. Both paths end at the
  same MCP query surface.
- Netdata's clickhouse collector emits 50 context(s) under `clickhouse.*`. The rule files enumerate
  which contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the ClickHouse service is up. Query Netdata via MCP with `list_nodes` and filter by the
   host running the target. A missing node means the symptom is at the network or orchestrator
   layer, not inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **Merge Debt Spiral**. Inserts arrive faster than merges complete then part count grows
   then merge cost increases (more parts to combine) then merges fall further behind then eventually
   "too many parts" rejections halt writes. Inspect the rule file whose signals move first for this
   mode.
4. Check for **Memory Exhaustion**. Single large query with expansive GROUP BY or JOIN then OOM kill
   or query cancellation then cascading retries compound the problem. Inspect the rule file whose
   signals move first for this mode.
5. Check for **Replication Lag Cascade**. Network partition or ZK issues then replica falls behind
   then catch-up requires fetching many parts then disk/network saturation slows catch-up further.
   Inspect the rule file whose signals move first for this mode.
6. Check for **ZooKeeper/Keeper Saturation**. Too many tables, excessive DDL, or ZK disk bottleneck
   then coordination latency spikes then session timeouts then replicas become read-only then
   cluster-wide write failure. Inspect the rule file whose signals move first for this mode.
7. Check for **Disk Space Collapse**. Merges need free space to write merged parts before deleting
   originals. Disk at 85-90% then merges cannot complete then small parts pile up consuming more
   metadata space then death spiral. Inspect the rule file whose signals move first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from ClickHouse
list_metrics with q="clickhouse"

# Pull a specific context over the last window
query_metrics with context="clickhouse.connections", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="clickhouse.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating ClickHouse as a generic HTTP or process health check. ClickHouse has specific failure
  archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed ClickHouse traffic
  before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the ClickHouse service. Every context
listed below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="clickhouse" (returns every clickhouse.* context Netdata sees)
2. query_metrics with contexts=[clickhouse.connections, clickhouse.uptime, clickhouse.queries, clickhouse.select_queries, clickhouse.insert_queries, clickhouse.io_errors] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="clickhouse.*"
```

Load-bearing contexts for this service:

- `clickhouse.connections`: Connections (connections). Dimensions: tcp, http, mysql, postgresql,
                            interserver.
- `clickhouse.uptime`: Uptime (seconds). Dimensions: uptime.
- `clickhouse.queries`: Queries (queries/s). Dimensions: successful, failed.
- `clickhouse.select_queries`: Select queries (selects/s). Dimensions: successful, failed.
- `clickhouse.insert_queries`: Insert queries (inserts/s). Dimensions: successful, failed.
- `clickhouse.io_errors`: Read and write errors (errors/s). Dimensions: read, write.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for ClickHouse:

- Host-resource pressure masquerading as application bug.
- Dependent service (DB, cache, upstream) causing a secondary symptom in the instrumented service.
- Configuration change that was never reloaded (some subsystems only pick up config on full
  restart).

Escalate by widening the query window: 2-6 hours instead of 15 minutes. Slow-moving causes are
invisible at triage window sizes.

## References

- [`rules/availability.md`](./rules/availability.md)
- [`rules/internal-state-parts-and-merges.md`](./rules/internal-state-parts-and-merges.md)
- [`rules/insert-health.md`](./rules/insert-health.md)
- [`rules/memory.md`](./rules/memory.md)
- [`rules/errors.md`](./rules/errors.md)
- [`rules/disk.md`](./rules/disk.md)
- [`rules/latency.md`](./rules/latency.md)
- [`rules/concurrency.md`](./rules/concurrency.md)
- [`rules/saturation.md`](./rules/saturation.md)
- [`rules/throughput.md`](./rules/throughput.md)
- [`rules/security-integrity.md`](./rules/security-integrity.md)
- Netdata operator playbook: the authoritative source material this skill summarizes.
- `skills/netdata-mcp-integration/` for the transport setup.
- `skills/netdata-otel-setup/` if additional application signals are needed beyond what Netdata
  collects natively.
