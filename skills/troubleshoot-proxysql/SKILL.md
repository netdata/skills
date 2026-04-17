---
name: troubleshoot-proxysql
description: "Use when diagnosing issues with Proxysql: backend connection starvation, multiplexing collapse, monitor false decisions, query rule cpu overload, or configuration drift. Queries Netdata via MCP for backend server health status, monitor health check results, backend connection pool usage, client connection metrics, questions rate, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - proxysql
---

# Troubleshoot Proxysql

## When to use this skill

- **Backend Connection Starvation**: Backend pool saturates. New queries queue or timeout.
- **Multiplexing Collapse**: Too many pinned sessions. Approaches 1:1 client-to-backend ratio.
- **Monitor False Decisions**: Health checks misconfigured. Backends flap between ONLINE and
                               SHUNNED.
- **Query Rule CPU Overload**: Complex regex in `mysql_query_rules` saturates worker threads.
- **Configuration Drift**: Changes not propagated between RUNTIME/MEMORY/DISK layers.
- **Cache Stampede**: Hot cache entry expires, thundering herd hits backend.
- Any time the user reports a Proxysql service behaving outside its expected envelope (elevated
  errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a Proxysql instance and wants a
  structured triage path.

## Key facts

- This skill wraps the Netdata operator playbook for Proxysql. It does not replace the playbook; it
  routes a coding agent through MCP queries against the same signals the playbook relies on.
- ProxySQL is a high-performance MySQL protocol-aware proxy that sits between application clients
  and MySQL-compatible backends (MySQL, MariaDB, Percona). It is **not** a TCP relay; it fully
  parses the MySQL wire protocol and makes routing, caching, and connection management decisions per
  query.
- The playbook decomposes Proxysql health into 7 signal domains: Availability & Backend Health,
  Connection Management, Query Performance, Error Tracking, Traffic & Throughput, Resource
  Utilization. Each domain maps to one rule file in this skill.
- Dominant failure archetypes the playbook calls out: Backend Connection Starvation; Multiplexing
  Collapse; Monitor False Decisions; Query Rule CPU Overload; Configuration Drift.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your Proxysql instrumentation adds. Both paths end at the same
  MCP query surface.

## Step-by-step

1. Confirm the Proxysql service is up. Query Netdata via MCP with `list_nodes` and filter by the
   host running the target. A missing node means the symptom is at the network or orchestrator
   layer, not inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **Backend Connection Starvation**. Backend pool saturates. New queries queue or
   timeout. Inspect the rule file whose signals move first for this mode.
4. Check for **Multiplexing Collapse**. Too many pinned sessions. Approaches 1:1 client-to-backend
   ratio. Inspect the rule file whose signals move first for this mode.
5. Check for **Monitor False Decisions**. Health checks misconfigured. Backends flap between ONLINE
   and SHUNNED. Inspect the rule file whose signals move first for this mode.
6. Check for **Query Rule CPU Overload**. Complex regex in `mysql_query_rules` saturates worker
   threads. Inspect the rule file whose signals move first for this mode.
7. Check for **Configuration Drift**. Changes not propagated between RUNTIME/MEMORY/DISK layers.
   Inspect the rule file whose signals move first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from Proxysql
list_metrics with optional filter by context prefix

# Pull a specific signal over the last window
query_metrics with context=<signal>, relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with host=<host> or service=<service>

# Correlate a known problem signal with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating Proxysql as a generic HTTP or process health check. Proxysql has specific failure
  archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed Proxysql traffic
  before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the Proxysql service:

```text
1. list_metrics filtered by the Proxysql service's context prefix.
2. query_metrics for the key signals from the first-triggered domain over the last 30 minutes.
3. find_anomalous_metrics scoped to the same service/time window.
```

Signals the playbook considers load-bearing:

  - Backend Server Health Status
  - Monitor Health Check Results
  - Frontend Listener Liveness
  - Backend Connection Pool Usage
  - Client Connection Metrics
  - Per-User Connection Utilization

A clean result means every key signal is within its expected band and the `find_anomalous_metrics`
list is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for Proxysql:

- Host-resource pressure masquerading as application bug.
- Dependent service (DB, cache, upstream) causing a secondary symptom in the instrumented service.
- Configuration change that was never reloaded (some subsystems only pick up config on full
  restart).

Escalate by widening the query window: 2-6 hours instead of 15 minutes. Slow-moving causes are
invisible at triage window sizes.

## References

- [`rules/availability-backend-health.md`](./rules/availability-backend-health.md)
- [`rules/connection-management.md`](./rules/connection-management.md)
- [`rules/query-performance.md`](./rules/query-performance.md)
- [`rules/error-tracking.md`](./rules/error-tracking.md)
- [`rules/traffic-throughput.md`](./rules/traffic-throughput.md)
- [`rules/resource-utilization.md`](./rules/resource-utilization.md)
- [`rules/cluster-replication-integrity.md`](./rules/cluster-replication-integrity.md)
- Netdata operator playbook: the authoritative source material this skill summarizes.
- `skills/netdata-mcp-integration/` for the transport setup.
- `skills/netdata-otel-setup/` if additional application signals are needed beyond what Netdata
  collects natively.
