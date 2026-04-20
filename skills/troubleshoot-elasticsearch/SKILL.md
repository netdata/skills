---
name: troubleshoot-elasticsearch
description: "Use when diagnosing issues with Elasticsearch: heap pressure death spiral, shard overallocation, disk watermark cascade, mapping explosion, or merge storms. Queries Netdata via MCP for Elasticsearch health signals, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - elasticsearch
---

# Troubleshoot Elasticsearch

## When to use this skill

- **Heap Pressure Death Spiral**: Too much data in heap then frequent old-gen GC then long
                                  stop-the-world pauses then node misses fault detection checks then
                                  master removes node then triggers shard reallocation then more
                                  heap pressure on remaining nodes then cascade.
- **Shard Overallocation**: Too many shards (thousands per node). Each shard carries fixed overhead
                            (segment metadata per field, thread contexts, buffers). Cluster becomes
                            slow to manage, cluster state balloons, master nodes struggle.
- **Disk Watermark Cascade**: Nodes hit high watermark then allocator relocates shards then target
                              nodes approach watermark then relocations fail then flood stage then
                              indices go read-only then writes fail. Block is automatically removed
                              when disk drops below high watermark (7.x+, 8.x).
- **Mapping Explosion**: Dynamic mapping creates a new field for every unique key then mappings with
                         tens of thousands of fields then cluster state balloons then heap usage
                         grows on every node then master instability.
- **Merge Storms**: Bulk indexing creates many small segments then merge policy falls behind then
                    search performance degrades then segment count and file descriptors grow then
                    merge backlog compounds.
- **Master Instability**: Master overwhelmed by cluster state updates (index creation/deletion,
                          mapping changes, shard allocation) then election timeouts then all writes
                          and administrative operations stall.
- Any time the user reports a Elasticsearch service behaving outside its expected envelope (elevated
  errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a Elasticsearch instance and wants a
  structured triage path.

## Key facts

- This skill wraps the Netdata operator playbook for Elasticsearch. It does not replace the
  playbook; it routes a coding agent through MCP queries against the same signals the playbook
  relies on.
- Elasticsearch is a distributed search and analytics engine built on Apache Lucene. Every node runs
  several interacting subsystems that compete for the same resources. An operator must reason about
  these subsystems and their interactions to diagnose failures correctly.
- Dominant failure archetypes the playbook calls out: Heap Pressure Death Spiral; Shard
  Overallocation; Disk Watermark Cascade; Mapping Explosion; Merge Storms.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your Elasticsearch instrumentation adds. Both paths end at the
  same MCP query surface.
- Netdata's elasticsearch collector emits 92 context(s) under `elasticsearch.*`. The rule files
  enumerate which contexts surface which domain; the Verification section below names the
  load-bearing ones explicitly.

## Step-by-step

1. Confirm the Elasticsearch service is up. Query Netdata via MCP with `list_nodes` and filter by
   the host running the target. A missing node means the symptom is at the network or orchestrator
   layer, not inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **Heap Pressure Death Spiral**. Too much data in heap then frequent old-gen GC then
   long stop-the-world pauses then node misses fault detection checks then master removes node then
   triggers shard reallocation then more heap pressure on remaining nodes then cascade. Inspect the
   rule file whose signals move first for this mode.
4. Check for **Shard Overallocation**. Too many shards (thousands per node). Each shard carries
   fixed overhead (segment metadata per field, thread contexts, buffers). Cluster becomes slow to
   manage, cluster state balloons, master nodes struggle. Inspect the rule file whose signals move
   first for this mode.
5. Check for **Disk Watermark Cascade**. Nodes hit high watermark then allocator relocates shards
   then target nodes approach watermark then relocations fail then flood stage then indices go
   read-only then writes fail. Block is automatically removed when disk drops below high watermark
   (7.x+, 8.x). Inspect the rule file whose signals move first for this mode.
6. Check for **Mapping Explosion**. Dynamic mapping creates a new field for every unique key then
   mappings with tens of thousands of fields then cluster state balloons then heap usage grows on
   every node then master instability. Inspect the rule file whose signals move first for this mode.
7. Check for **Merge Storms**. Bulk indexing creates many small segments then merge policy falls
   behind then search performance degrades then segment count and file descriptors grow then merge
   backlog compounds. Inspect the rule file whose signals move first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from Elasticsearch
list_metrics with q="elasticsearch"

# Pull a specific context over the last window
query_metrics with context="elasticsearch.node_http_connections", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="elasticsearch.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating Elasticsearch as a generic HTTP or process health check. Elasticsearch has specific
  failure archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed Elasticsearch traffic
  before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the Elasticsearch service. Every
context listed below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="elasticsearch" (returns every elasticsearch.* context Netdata sees)
2. query_metrics with contexts=[elasticsearch.node_http_connections, elasticsearch.cluster_health_status, elasticsearch.node_index_health, elasticsearch.node_thread_pool_rejected, elasticsearch.node_indices_indexing, elasticsearch.node_indices_indexing_current] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="elasticsearch.*"
```

Load-bearing contexts for this service:

- `elasticsearch.node_http_connections`: HTTP Connections (connections). Dimensions: open.
- `elasticsearch.cluster_health_status`: Cluster Status (status). Dimensions: green, yellow, red.
- `elasticsearch.node_index_health`: Index Health (status). Dimensions: green, yellow, red.
- `elasticsearch.node_thread_pool_rejected`: Thread Pool Rejected Threads Count (threads).
                                             Dimensions: generic, search, search_throttled, get,
                                             analyze, write.
- `elasticsearch.node_indices_indexing`: Indexing Operations (operations/s). Dimensions: index.
- `elasticsearch.node_indices_indexing_current`: Indexing Operations Current (operations).
                                                 Dimensions: index.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for Elasticsearch:

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
