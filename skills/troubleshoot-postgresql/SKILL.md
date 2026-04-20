---
name: troubleshoot-postgresql
description: "Use when diagnosing issues with PostgreSQL: connection exhaustion, lock contention cascade, autovacuum starvation / bloat spiral, transaction id wraparound emergency, or checkpoint storms. Queries Netdata via MCP for process liveness, recovery state, transaction rate (commits and rollbacks), row operations rate, query duration distribution, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - postgresql
---

# Troubleshoot PostgreSQL

## When to use this skill

- **Connection exhaustion**: All max_connections slots consumed then new connections rejected then
                             application cascade failure. Often triggered by slow queries holding
                             connections, application connection leaks, or missing connection
                             pooler.
- **Lock contention cascade**: One long-running transaction holds a lock then others queue behind it
                               then connection pool fills with waiting backends then new requests
                               can't be served. DDL operations (ALTER TABLE) are the most common
                               trigger.
- **Autovacuum starvation / bloat spiral**: Autovacuum can't keep up with dead tuple generation then
                                            tables grow unbounded then sequential scans slow then
                                            index bloat then query plans degrade. The slow-motion
                                            version takes weeks; the acute version (heavy write
                                            burst) takes hours.
- **Transaction ID wraparound emergency**: autovacuum_freeze_max_age (default 200M) exceeded then
                                           anti-wraparound vacuum forced then if it can't complete,
                                           PostgreSQL shuts down all writes at ~3M XIDs from
                                           wraparound (PG 14+) or ~1M (PG 13-). This is the only
                                           PostgreSQL failure that requires completing a vacuum
                                           before r...
- **Checkpoint storms**: Too many dirty pages accumulate then checkpoint flushes enormous I/O burst
                         then latency spike for all queries. Especially acute with spindle-based
                         storage or undersized max_wal_size.
- **Replication lag spiral**: Standby falls behind then if synchronous replication, primary write
                              latency increases then if using slots, WAL accumulates on primary then
                              disk fills then primary crashes.
- Any time the user reports a PostgreSQL service behaving outside its expected envelope (elevated
  errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a PostgreSQL instance and wants a
  structured triage path.

## Key facts

- This skill wraps the Netdata operator playbook for PostgreSQL. It does not replace the playbook;
  it routes a coding agent through MCP queries against the same signals the playbook relies on.
- PostgreSQL is a **process-per-connection** relational database. Every client connection spawns a
  dedicated OS process (backend) forked from the postmaster; the master process that manages the
  entire cluster. This means connection count maps directly to OS process count, memory consumption,
  and context-switching overhead. Understanding this architecture is essential for reasoning about
  failures.
- The playbook decomposes PostgreSQL health into 6 signal domains: Availability, Throughput,
  Latency, Internal State, Replication, Security & Integrity. Each domain maps to one rule file in
  this skill.
- Dominant failure archetypes the playbook calls out: Connection exhaustion; Lock contention
  cascade; Autovacuum starvation / bloat spiral; Transaction ID wraparound emergency; Checkpoint
  storms.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your PostgreSQL instrumentation adds. Both paths end at the
  same MCP query surface.
- Netdata's postgres collector emits 70 context(s) under `postgres.*`. The rule files enumerate
  which contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the PostgreSQL service is up. Query Netdata via MCP with `list_nodes` and filter by the
   host running the target. A missing node means the symptom is at the network or orchestrator
   layer, not inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **Connection exhaustion**. All max_connections slots consumed then new connections
   rejected then application cascade failure. Often triggered by slow queries holding connections,
   application connection leaks, or missing connection pooler. Inspect the rule file whose signals
   move first for this mode.
4. Check for **Lock contention cascade**. One long-running transaction holds a lock then others
   queue behind it then connection pool fills with waiting backends then new requests can't be
   served. DDL operations (ALTER TABLE) are the most common trigger. Inspect the rule file whose
   signals move first for this mode.
5. Check for **Autovacuum starvation / bloat spiral**. Autovacuum can't keep up with dead tuple
   generation then tables grow unbounded then sequential scans slow then index bloat then query
   plans degrade. The slow-motion version takes weeks; the acute version (heavy write burst) takes
   hours. Inspect the rule file whose signals move first for this mode.
6. Check for **Transaction ID wraparound emergency**. autovacuum_freeze_max_age (default 200M)
   exceeded then anti-wraparound vacuum forced then if it can't complete, PostgreSQL shuts down all
   writes at ~3M XIDs from wraparound (PG 14+) or ~1M (PG 13-). This is the only PostgreSQL failure
   that requires completing a vacuum before recovery; no workaround. Inspect the rule file whose
   signals move first for this mode.
7. Check for **Checkpoint storms**. Too many dirty pages accumulate then checkpoint flushes enormous
   I/O burst then latency spike for all queries. Especially acute with spindle-based storage or
   undersized max_wal_size. Inspect the rule file whose signals move first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from PostgreSQL
list_metrics with q="postgres"

# Pull a specific context over the last window
query_metrics with context="postgres.connections_utilization", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="postgres.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating PostgreSQL as a generic HTTP or process health check. PostgreSQL has specific failure
  archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed PostgreSQL traffic
  before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the PostgreSQL service. Every context
listed below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="postgres" (returns every postgres.* context Netdata sees)
2. query_metrics with contexts=[postgres.connections_utilization, postgres.connections_usage, postgres.connections_state_count, postgres.uptime, postgres.db_connections_utilization, postgres.db_connections_count] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="postgres.*"
```

Load-bearing contexts for this service:

- `postgres.connections_utilization`: Connections utilization (percentage). Dimensions: used.
- `postgres.connections_usage`: Connections usage (connections). Dimensions: available, used.
- `postgres.connections_state_count`: Connections in each state (connections). Dimensions: active,
                                      idle, idle_in_transaction, idle_in_transaction_aborted,
                                      disabled.
- `postgres.uptime`: Uptime (seconds). Dimensions: uptime.
- `postgres.db_connections_utilization`: Database connections utilization (percentage). Dimensions:
                                         used.
- `postgres.db_connections_count`: Database connections (connections). Dimensions: connections.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for PostgreSQL:

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
- [`rules/internal-state.md`](./rules/internal-state.md)
- [`rules/replication.md`](./rules/replication.md)
- [`rules/security-integrity.md`](./rules/security-integrity.md)
- Netdata operator playbook: the authoritative source material this skill summarizes.
- `skills/netdata-mcp-integration/` for the transport setup.
- `skills/netdata-otel-setup/` if additional application signals are needed beyond what Netdata
  collects natively.
