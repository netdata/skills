---
name: troubleshoot-coredns
description: "Use when diagnosing issues with CoreDNS: upstream black hole, cache collapse (thundering herd), kubernetes api disconnect, memory blowout, or forwarding loop. Queries Netdata via MCP for CoreDNS health signals, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - coredns
---

# Troubleshoot CoreDNS

## When to use this skill

- **Upstream black hole**: All upstream DNS servers unreachable. Forward plugin fails immediately
                           then SERVFAIL cascade to all clients. Latency is low (fast failure), not
                           high.
- **Cache collapse (thundering herd)**: After restart or cache eviction, all clients simultaneously
                                        re-query the same records. Upstream flood can cause cascade
                                        failure.
- **Kubernetes API disconnect**: API server unreachable. CoreDNS serves stale data from last known
                                 state (no immediate SERVFAIL), but new services are invisible.
                                 Gradual degradation as state drifts.
- **Memory blowout**: Unbounded cache growth or goroutine leak then OOM kill by container runtime.
                      Cliff-edge failure with no gradual degradation.
- **Forwarding loop**: Misconfiguration causes CoreDNS to forward to itself. The `loop` plugin
                       detects this at startup and crashes (`log.Fatalf` then `os.Exit(1)`), causing
                       CrashLoopBackOff in Kubernetes. Only detects loops at startup, not runtime.
- **UDP buffer cliff**: Kernel UDP receive buffer fills then packets dropped silently before
                        reaching CoreDNS. CoreDNS metrics look "too good to be true" (low latency,
                        no errors, but low throughput).
- Any time the user reports a CoreDNS service behaving outside its expected envelope (elevated
  errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a CoreDNS instance and wants a structured
  triage path.

## Key facts

- This skill wraps the Netdata operator playbook for CoreDNS. It does not replace the playbook; it
  routes a coding agent through MCP queries against the same signals the playbook relies on.
- CoreDNS is a DNS server written in Go, built around a **plugin chain architecture**. Every DNS
  query traverses an ordered chain of plugins defined in the `Corefile`. Each plugin can inspect,
  modify, respond to, or pass along the query. This is a pipeline; understanding the pipeline is the
  key to understanding every failure mode.
- Dominant failure archetypes the playbook calls out: Upstream black hole; Cache collapse
  (thundering herd); Kubernetes API disconnect; Memory blowout; Forwarding loop.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your CoreDNS instrumentation adds. Both paths end at the same
  MCP query surface.
- Netdata's coredns collector emits 22 context(s) under `coredns.*`. The rule files enumerate which
  contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the CoreDNS service is up. Query Netdata via MCP with `list_nodes` and filter by the host
   running the target. A missing node means the symptom is at the network or orchestrator layer, not
   inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **Upstream black hole**. All upstream DNS servers unreachable. Forward plugin fails
   immediately then SERVFAIL cascade to all clients. Latency is low (fast failure), not high.
   Inspect the rule file whose signals move first for this mode.
4. Check for **Cache collapse (thundering herd)**. After restart or cache eviction, all clients
   simultaneously re-query the same records. Upstream flood can cause cascade failure. Inspect the
   rule file whose signals move first for this mode.
5. Check for **Kubernetes API disconnect**. API server unreachable. CoreDNS serves stale data from
   last known state (no immediate SERVFAIL), but new services are invisible. Gradual degradation as
   state drifts. Inspect the rule file whose signals move first for this mode.
6. Check for **Memory blowout**. Unbounded cache growth or goroutine leak then OOM kill by container
   runtime. Cliff-edge failure with no gradual degradation. Inspect the rule file whose signals move
   first for this mode.
7. Check for **Forwarding loop**. Misconfiguration causes CoreDNS to forward to itself. The `loop`
   plugin detects this at startup and crashes (`log.Fatalf` then `os.Exit(1)`), causing
   CrashLoopBackOff in Kubernetes. Only detects loops at startup, not runtime. Inspect the rule file
   whose signals move first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from CoreDNS
list_metrics with q="coredns"

# Pull a specific context over the last window
query_metrics with context="coredns.dns_request_count_total_per_status", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="coredns.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating CoreDNS as a generic HTTP or process health check. CoreDNS has specific failure
  archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed CoreDNS traffic
  before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the CoreDNS service. Every context
listed below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="coredns" (returns every coredns.* context Netdata sees)
2. query_metrics with contexts=[coredns.dns_request_count_total_per_status, coredns.server_request_count_total_per_status, coredns.dns_no_matching_zone_dropped_total, coredns.dns_responses_count_total_per_rcode, coredns.server_responses_count_total_per_rcode, coredns.zone_responses_count_total_per_rcode] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="coredns.*"
```

Load-bearing contexts for this service:

- `coredns.dns_request_count_total_per_status`: Number Of Processed And Dropped DNS Requests
                                                (requests/s). Dimensions: processed, dropped.
- `coredns.server_request_count_total_per_status`: Number Of Processed And Dropped DNS Requests
                                                   (requests/s). Dimensions: processed, dropped.
- `coredns.dns_no_matching_zone_dropped_total`: Number Of Dropped DNS Requests Because Of No
                                                Matching Zone (requests/s). Dimensions: dropped.
- `coredns.dns_responses_count_total_per_rcode`: Number Of DNS Responses Per Rcode (responses/s).
                                                 Dimensions: noerror, formerr, servfail, nxdomain,
                                                 notimp, refused.
- `coredns.server_responses_count_total_per_rcode`: Number Of DNS Responses Per Rcode (responses/s).
                                                    Dimensions: noerror, formerr, servfail,
                                                    nxdomain, notimp, refused.
- `coredns.zone_responses_count_total_per_rcode`: Number Of DNS Responses Per Rcode (responses/s).
                                                  Dimensions: noerror, formerr, servfail, nxdomain,
                                                  notimp, refused.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for CoreDNS:

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
