---
name: troubleshoot-kubernetes-kube-proxy
description: "Use when diagnosing issues with Kubernetes Kube Proxy: \"stale rules / zombie watch\", \"conntrack table full\", or \"sync loop storm\". Queries Netdata via MCP for Kubernetes Kube Proxy health signals, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - kubernetes-kube-proxy
---

# Troubleshoot Kubernetes Kube Proxy

## When to use this skill

- **"Stale Rules / Zombie Watch"**: Watch connection lost silently. kube-proxy appears healthy but operates on stale state. New Services unreachable; traffic routes to dead Pods. Insidious because healthz may still report 200.
- **"Conntrack Table Full"**: Node conntrack table fills. New connections dropped silently (SYN dropped, no application error). Affects ALL node traffic, not just Service traffic. Cliff-edge failure; works fine until full, then instant catastrophe.
- **"Sync Loop Storm"**: In iptables mode with high endpoint churn, each sync takes seconds and can't keep up. Queue grows, CPU spikes, rules are perpetually stale. Degenerate state: never converges.
- **"iptables Lock Starvation"**: Another process holds the xtables lock for extended periods. kube-proxy's 5-second timeout expires, sync fails. May repeat for days without triggering unhealthy status (bug #105742).
- **"Silent Conntrack Leak"**: TCP conntrack entries accumulate because kube-proxy doesn't clean them. Long-lived TCP connections to removed endpoints hold entries for up to 5 days (432,000s established timeout).
- **"Failed Restore, Lost Changes"**: iptables-restore fails but kube-proxy has already cleared its change tracking (bug #112604). UDP conntrack deletions and endpoint changes silently lost forever. Next sync sees no pending changes.
- Any time the user reports a Kubernetes Kube Proxy service behaving outside its expected envelope (elevated errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a Kubernetes Kube Proxy instance and wants a structured triage path.

## Key facts

- This skill wraps the Netdata operator playbook for Kubernetes Kube Proxy. It does not replace the playbook; it routes a coding agent through MCP queries against the same signals the playbook relies on.
- kube-proxy is a network-plane control loop running on every node in a Kubernetes cluster. Despite the name, it does **not** proxy traffic in the data path. It programs the node's kernel networking subsystem; iptables rules, IPVS virtual servers, or nftables rules; so that traffic destined for a Service ClusterIP or NodePort is DNAT'd to a healthy backend Pod endpoint. It is a control-plane comp...
- Dominant failure archetypes the playbook calls out: "Stale Rules / Zombie Watch"; "Conntrack Table Full"; "Sync Loop Storm"; "iptables Lock Starvation"; "Silent Conntrack Leak".
- Netdata observes the signals listed in the rule files via its native collectors, plus any OpenTelemetry-shipped metrics that your Kubernetes Kube Proxy instrumentation adds. Both paths end at the same MCP query surface.

## Step-by-step

1. Confirm the Kubernetes Kube Proxy service is up. Query Netdata via MCP with `list_nodes` and filter by the host running the target. A missing node means the symptom is at the network or orchestrator layer, not inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window; anomalies frame which rule file to read first.
3. Check for **"Stale Rules / Zombie Watch"**. Watch connection lost silently. kube-proxy appears healthy but operates on stale state. New Services unreachable; traffic routes to dead Pods. Insidious because healthz may still report 200. Inspect the rule file whose signals move first for this mode.
4. Check for **"Conntrack Table Full"**. Node conntrack table fills. New connections dropped silently (SYN dropped, no application error). Affects ALL node traffic, not just Service traffic. Cliff-edge failure; works fine until full, then instant catastrophe. Inspect the rule file whose signals move first for this mode.
5. Check for **"Sync Loop Storm"**. In iptables mode with high endpoint churn, each sync takes seconds and can't keep up. Queue grows, CPU spikes, rules are perpetually stale. Degenerate state: never converges. Inspect the rule file whose signals move first for this mode.
6. Check for **"iptables Lock Starvation"**. Another process holds the xtables lock for extended periods. kube-proxy's 5-second timeout expires, sync fails. May repeat for days without triggering unhealthy status (bug #105742). Inspect the rule file whose signals move first for this mode.
7. Check for **"Silent Conntrack Leak"**. TCP conntrack entries accumulate because kube-proxy doesn't clean them. Long-lived TCP connections to removed endpoints hold entries for up to 5 days (432,000s established timeout). Inspect the rule file whose signals move first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`, `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the MCP queries from the Verification section to confirm the signals returned to expected ranges. A fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from Kubernetes Kube Proxy
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

- Treating Kubernetes Kube Proxy as a generic HTTP or process health check. Kubernetes Kube Proxy has specific failure archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed Kubernetes Kube Proxy traffic before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the Kubernetes Kube Proxy service:

```text
1. list_metrics filtered by the Kubernetes Kube Proxy service's context prefix.
2. query_metrics for the key signals from the first-triggered domain over the last 30 minutes.
3. find_anomalous_metrics scoped to the same service/time window.
```

Signals the playbook considers load-bearing:

  - the specific signals listed in the domain rule files

A clean result means every key signal is within its expected band and the `find_anomalous_metrics` list is empty or contains only already-acknowledged items. If the fix was real, re-running the same queries 10 minutes after applying it will show a clean result. If it does not, revert and look deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was deeper than the applied change. Typical misdiagnoses for Kubernetes Kube Proxy:

- Host-resource pressure masquerading as application bug.
- Dependent service (DB, cache, upstream) causing a secondary symptom in the instrumented service.
- Configuration change that was never reloaded (some subsystems only pick up config on full restart).

Escalate by widening the query window: 2-6 hours instead of 15 minutes. Slow-moving causes are invisible at triage window sizes.

## References

- [`rules/overview.md`](./rules/overview.md)
- Netdata operator playbook: the authoritative source material this skill summarizes.
- `skills/netdata-mcp-integration/` for the transport setup.
- `skills/netdata-otel-setup/` if additional application signals are needed beyond what Netdata collects natively.
