---
name: troubleshoot-pgbouncer
description: "Use when diagnosing issues with PgBouncer: pool exhaustion, client connection limit, file descriptor exhaustion, backend unreachable, or pool mode mismatch. Queries Netdata via MCP for PgBouncer health signals, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - pgbouncer
---

# Troubleshoot PgBouncer

## When to use this skill

- **Pool exhaustion**: All server connections busy then clients queue then wait times grow then
                       application timeouts then cascading retries (thundering herd). This is the
                       most common PgBouncer incident.
- **Client connection limit**: `max_client_conn` reached then new connections rejected with `"no
                               more connections allowed (max_client_conn)"`. Often caused by
                               `max_client_conn` exceeding the FD limit.
- **File descriptor exhaustion**: OS `ulimit` reached then cannot accept new connections, cannot
                                  open log files. PgBouncer may crash-loop. Usually happens when
                                  `max_client_conn` is set higher than the FD limit.
- **Backend unreachable**: PostgreSQL down, network partition, or DNS failure then server
                           connections cannot be established then clients queue indefinitely then
                           `query_wait_timeout` fires.
- **Pool mode mismatch**: Application uses session-dependent features (prepared statements, temp
                          tables, `LISTEN/NOTIFY`, advisory locks, `SET` variables) in transaction
                          pooling mode then silent data corruption or "does not exist" errors. This
                          is the most insidious failure because it looks like an appl...
- **Connection leak**: Applications hold connections without releasing them (long-running idle
                       transactions in session mode, or abandoned connections) then pool exhaustion
                       even under light load.
- Any time the user reports a PgBouncer service behaving outside its expected envelope (elevated
  errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a PgBouncer instance and wants a
  structured triage path.

## Key facts

- This skill wraps the Netdata operator playbook for PgBouncer. It does not replace the playbook; it
  routes a coding agent through MCP queries against the same signals the playbook relies on.
- PgBouncer is a **single-threaded, event-driven connection multiplexer** that sits between
  application clients and PostgreSQL backends. Its entire purpose is to reduce the number of actual
  PostgreSQL connections by sharing a smaller pool of server connections across many client
  connections.
- Dominant failure archetypes the playbook calls out: Pool exhaustion; Client connection limit; File
  descriptor exhaustion; Backend unreachable; Pool mode mismatch.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your PgBouncer instrumentation adds. Both paths end at the same
  MCP query surface.
- Netdata's pgbouncer collector emits 13 context(s) under `pgbouncer.*`. The rule files enumerate
  which contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the PgBouncer service is up. Query Netdata via MCP with `list_nodes` and filter by the
   host running the target. A missing node means the symptom is at the network or orchestrator
   layer, not inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **Pool exhaustion**. All server connections busy then clients queue then wait times
   grow then application timeouts then cascading retries (thundering herd). This is the most common
   PgBouncer incident. Inspect the rule file whose signals move first for this mode.
4. Check for **Client connection limit**. `max_client_conn` reached then new connections rejected
   with `"no more connections allowed (max_client_conn)"`. Often caused by `max_client_conn`
   exceeding the FD limit. Inspect the rule file whose signals move first for this mode.
5. Check for **File descriptor exhaustion**. OS `ulimit` reached then cannot accept new connections,
   cannot open log files. PgBouncer may crash-loop. Usually happens when `max_client_conn` is set
   higher than the FD limit. Inspect the rule file whose signals move first for this mode.
6. Check for **Backend unreachable**. PostgreSQL down, network partition, or DNS failure then server
   connections cannot be established then clients queue indefinitely then `query_wait_timeout`
   fires. Inspect the rule file whose signals move first for this mode.
7. Check for **Pool mode mismatch**. Application uses session-dependent features (prepared
   statements, temp tables, `LISTEN/NOTIFY`, advisory locks, `SET` variables) in transaction pooling
   mode then silent data corruption or "does not exist" errors. This is the most insidious failure
   because it looks like an application bug, not an infrastructure issue. Inspect the rule file
   whose signals move first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from PgBouncer
list_metrics with q="pgbouncer"

# Pull a specific context over the last window
query_metrics with context="pgbouncer.client_connections_utilization", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="pgbouncer.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating PgBouncer as a generic HTTP or process health check. PgBouncer has specific failure
  archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed PgBouncer traffic
  before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the PgBouncer service. Every context
listed below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="pgbouncer" (returns every pgbouncer.* context Netdata sees)
2. query_metrics with contexts=[pgbouncer.client_connections_utilization, pgbouncer.db_client_connections, pgbouncer.db_server_connections, pgbouncer.db_server_connections_utilization, pgbouncer.db_queries, pgbouncer.db_queries_time] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="pgbouncer.*"
```

Load-bearing contexts for this service:

- `pgbouncer.client_connections_utilization`: Client connections utilization (percentage).
                                              Dimensions: used.
- `pgbouncer.db_client_connections`: Database client connections (connections). Dimensions: active,
                                     waiting, cancel_req.
- `pgbouncer.db_server_connections`: Database server connections (connections). Dimensions: active,
                                     idle, used, tested, login.
- `pgbouncer.db_server_connections_utilization`: Database server connections utilization
                                                 (percentage). Dimensions: used.
- `pgbouncer.db_queries`: Database pooled SQL queries (queries/s). Dimensions: queries.
- `pgbouncer.db_queries_time`: Database queries time (seconds). Dimensions: time.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for PgBouncer:

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
