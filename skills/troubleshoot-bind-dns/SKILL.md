---
name: troubleshoot-bind-dns
description: "Use when diagnosing issues with BIND DNS: recursive client exhaustion, cache pressure spiral, or upstream dependency failure. Queries Netdata via MCP for BIND DNS health signals, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - bind-dns
---

# Troubleshoot BIND DNS

## When to use this skill

- **Recursive client exhaustion**: Outstanding fetches pile up (slow upstream), fill the
                                   `recursive-clients` table, new queries get SERVFAIL; cliff-edge
                                   failure.
- **Cache pressure spiral**: Undersized cache then low hit ratio then more upstream queries then
                             more latency then more concurrent fetches then resource exhaustion.
- **Upstream dependency failure**: Forwarders or upstream nameservers slow/unreachable then queries
                                   hang for timeout duration (default 10s × 3 retries = 30s per
                                   slot) then slots consumed then broad SERVFAIL.
- **UDP packet drops**: Kernel receive buffer overflow then packets lost before BIND sees them then
                        invisible query loss.
- **Zone staleness cascade**: Transfer failures then secondary serves stale data then SOA expire
                              reached then zone removed then SERVFAIL/NXDOMAIN.
- **DNSSEC time bomb**: Signing stalls then signatures expire then validating resolvers worldwide
                        reject zone then widespread SERVFAIL for signed domains.
- Any time the user reports a BIND DNS service behaving outside its expected envelope (elevated
  errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a BIND DNS instance and wants a
  structured triage path.

## Key facts

- This skill wraps the Netdata operator playbook for BIND DNS. It does not replace the playbook; it
  routes a coding agent through MCP queries against the same signals the playbook relies on.
- BIND (`named`) is a single daemon that processes DNS queries through a pipeline: **receive packet
  then parse then ACL/view check then cache lookup (if recursive) then zone lookup (if
  authoritative) then recursive fetch to upstream (if cache miss and recursion enabled) then apply
  RPZ/DNSSEC then serialize response then send**.
- Dominant failure archetypes the playbook calls out: Recursive client exhaustion; Cache pressure
  spiral; Upstream dependency failure; UDP packet drops; Zone staleness cascade.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your BIND DNS instrumentation adds. Both paths end at the same
  MCP query surface.

## Step-by-step

1. Confirm the BIND DNS service is up. Query Netdata via MCP with `list_nodes` and filter by the
   host running the target. A missing node means the symptom is at the network or orchestrator
   layer, not inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **Recursive client exhaustion**. Outstanding fetches pile up (slow upstream), fill the
   `recursive-clients` table, new queries get SERVFAIL; cliff-edge failure. Inspect the rule file
   whose signals move first for this mode.
4. Check for **Cache pressure spiral**. Undersized cache then low hit ratio then more upstream
   queries then more latency then more concurrent fetches then resource exhaustion. Inspect the rule
   file whose signals move first for this mode.
5. Check for **Upstream dependency failure**. Forwarders or upstream nameservers slow/unreachable
   then queries hang for timeout duration (default 10s × 3 retries = 30s per slot) then slots
   consumed then broad SERVFAIL. Inspect the rule file whose signals move first for this mode.
6. Check for **UDP packet drops**. Kernel receive buffer overflow then packets lost before BIND sees
   them then invisible query loss. Inspect the rule file whose signals move first for this mode.
7. Check for **Zone staleness cascade**. Transfer failures then secondary serves stale data then SOA
   expire reached then zone removed then SERVFAIL/NXDOMAIN. Inspect the rule file whose signals move
   first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from BIND DNS
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

- Treating BIND DNS as a generic HTTP or process health check. BIND DNS has specific failure
  archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed BIND DNS traffic
  before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the BIND DNS service:

```text
1. list_metrics filtered by the BIND DNS service's context prefix.
2. query_metrics for the key signals from the first-triggered domain over the last 30 minutes.
3. find_anomalous_metrics scoped to the same service/time window.
```

Signals the playbook considers load-bearing:

  - the specific signals listed in the domain rule files

A clean result means every key signal is within its expected band and the `find_anomalous_metrics`
list is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for BIND DNS:

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
