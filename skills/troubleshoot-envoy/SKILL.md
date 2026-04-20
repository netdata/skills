---
name: troubleshoot-envoy
description: "Use when diagnosing issues with Envoy: connection pool exhaustion cascade, memory pressure spiral, xds control plane disconnect, retry amplification, or stats cardinality explosion. Queries Netdata via MCP for server state, upstream host health, upstream request rate, downstream request rate, upstream request duration, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - envoy
---

# Troubleshoot Envoy

## When to use this skill

- **Connection pool exhaustion cascade**: Upstream is slow then connections held longer then pool
                                          fills then pending requests queue then queue overflows
                                          then 503s with response flag UO. Envoy appears "broken"
                                          but is protecting itself from the upstream.
- **Memory pressure spiral**: Large request/response bodies + buffering filters then heap grows then
                              overload manager triggers then starts refusing connections then
                              cascading backpressure.
- **xDS control plane disconnect**: Control plane goes down then Envoy keeps running with
                                    last-known-good config then new services/endpoints invisible
                                    then stale routing then silent misrouting or 503s for new
                                    services.
- **Retry amplification**: Aggressive retry config then upstream partial failure then retry storm
                           multiplies load 2x-3x then accelerates the failure retries are trying to
                           mask.
- **Stats cardinality explosion**: Dynamic route names or per-request metadata in stats tags then
                                   stats memory region fills then new stats silently fail to
                                   register then monitoring blind spots.
- **Hot restart race conditions**: New process starts before old finishes draining then brief period
                                   where neither process is fully healthy then connection drops
                                   during rollover.
- Any time the user reports a Envoy service behaving outside its expected envelope (elevated errors,
  latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a Envoy instance and wants a structured
  triage path.

## Key facts

- This skill wraps the Netdata operator playbook for Envoy. It does not replace the playbook; it
  routes a coding agent through MCP queries against the same signals the playbook relies on.
- Envoy is a multi-threaded, event-driven L4/L7 proxy written in C++. At runtime, it is continuously
  doing these things:
- - Accepting downstream TCP connections on listener sockets - Parsing protocols and applying filter
  chains (network filters then HTTP connection manager then HTTP filters then router) - Routing
  requests/streams to upstream clusters based on route tables - Managing per-worker, per-cluster,
  per-host upstream connection pools - Buffering request and response data through filter chains -
  Enforcing t...
- The playbook decomposes Envoy health into 7 signal domains: Availability, Throughput, Latency,
  Errors, Saturation, Internal State. Each domain maps to one rule file in this skill.
- Dominant failure archetypes the playbook calls out: Connection pool exhaustion cascade; Memory
  pressure spiral; xDS control plane disconnect; Retry amplification; Stats cardinality explosion.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your Envoy instrumentation adds. Both paths end at the same MCP
  query surface.
- Netdata's envoy collector emits 54 context(s) under `envoy.*`. The rule files enumerate which
  contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the Envoy service is up. Query Netdata via MCP with `list_nodes` and filter by the host
   running the target. A missing node means the symptom is at the network or orchestrator layer, not
   inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **Connection pool exhaustion cascade**. Upstream is slow then connections held longer
   then pool fills then pending requests queue then queue overflows then 503s with response flag UO.
   Envoy appears "broken" but is protecting itself from the upstream. Inspect the rule file whose
   signals move first for this mode.
4. Check for **Memory pressure spiral**. Large request/response bodies + buffering filters then heap
   grows then overload manager triggers then starts refusing connections then cascading
   backpressure. Inspect the rule file whose signals move first for this mode.
5. Check for **xDS control plane disconnect**. Control plane goes down then Envoy keeps running with
   last-known-good config then new services/endpoints invisible then stale routing then silent
   misrouting or 503s for new services. Inspect the rule file whose signals move first for this
   mode.
6. Check for **Retry amplification**. Aggressive retry config then upstream partial failure then
   retry storm multiplies load 2x-3x then accelerates the failure retries are trying to mask.
   Inspect the rule file whose signals move first for this mode.
7. Check for **Stats cardinality explosion**. Dynamic route names or per-request metadata in stats
   tags then stats memory region fills then new stats silently fail to register then monitoring
   blind spots. Inspect the rule file whose signals move first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from Envoy
list_metrics with q="envoy"

# Pull a specific context over the last window
query_metrics with context="envoy.server_connections_count", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="envoy.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating Envoy as a generic HTTP or process health check. Envoy has specific failure archetypes
  (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed Envoy traffic before
  escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the Envoy service. Every context listed
below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="envoy" (returns every envoy.* context Netdata sees)
2. query_metrics with contexts=[envoy.server_connections_count, envoy.server_parent_connections_count, envoy.server_uptime, envoy.cluster_manager_cluster_updates_rate, envoy.cluster_manager_cluster_updated_via_merge_rate, envoy.cluster_manager_update_merge_cancelled_rate] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="envoy.*"
```

Load-bearing contexts for this service:

- `envoy.server_connections_count`: Server current connections (connections). Dimensions:
                                    connections.
- `envoy.server_parent_connections_count`: Server current parent connections (connections).
                                           Dimensions: connections.
- `envoy.server_uptime`: Server uptime (seconds). Dimensions: uptime.
- `envoy.cluster_manager_cluster_updates_rate`: Cluster manager updates (updates/s). Dimensions:
                                                cluster.
- `envoy.cluster_manager_cluster_updated_via_merge_rate`: Cluster manager updates applied as merged
                                                          updates (updates/s). Dimensions:
                                                          via_merge.
- `envoy.cluster_manager_update_merge_cancelled_rate`: Cluster manager cancelled merged updates
                                                       (updates/s). Dimensions: merge_cancelled.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for Envoy:

- Host-resource pressure masquerading as application bug.
- Dependent service (DB, cache, upstream) causing a secondary symptom in the instrumented service.
- Configuration change that was never reloaded (some subsystems only pick up config on full
  restart).

Escalate by widening the query window: 2-6 hours instead of 15 minutes. Slow-moving causes are
invisible at triage window sizes.

## References

- [`rules/availability.md`](./rules/availability.md)
- [`rules/throughput.md`](./rules/throughput.md)
- [`rules/latency.md`](./rules/latency.md)
- [`rules/errors.md`](./rules/errors.md)
- [`rules/saturation.md`](./rules/saturation.md)
- [`rules/internal-state.md`](./rules/internal-state.md)
- [`rules/configuration-state.md`](./rules/configuration-state.md)
- Netdata operator playbook: the authoritative source material this skill summarizes.
- `skills/netdata-mcp-integration/` for the transport setup.
- `skills/netdata-otel-setup/` if additional application signals are needed beyond what Netdata
  collects natively.
