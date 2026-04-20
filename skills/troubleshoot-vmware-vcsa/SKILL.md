---
name: troubleshoot-vmware-vcsa
description: "Use when diagnosing issues with VMware vCenter Server Appliance (vCSA): certificate expiry cascade, disk space exhaustion on a specific partition, database bloat / stats table growth, vpxd memory exhaustion / crash loop, or service dependency deadlock. Queries Netdata via MCP for VMware vCenter Server Appliance (vCSA) health signals, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - vmware-vcsa
---

# Troubleshoot VMware vCenter Server Appliance (vCSA)

## When to use this skill

- **Certificate Expiry Cascade**: The most devastating and most common. STS certificates,
                                  VMCA-signed machine certificates, or solution user certificates
                                  expire. Authentication fails. Services cannot communicate. The
                                  entire management plane goes dark. The insidious part: the
                                  certificates may have been valid fo...
- **Disk Space Exhaustion on a Specific Partition**: vCSA has a non-obvious partition layout
                                                     (`/storage/log`, `/storage/db`,
                                                     `/storage/seat`, `/storage/updatemgr`,
                                                     `/storage/netdump`, `/storage/autodeploy`,
                                                     `/storage/imagebuilder`, `/storage/lifecycle`,
                                                     `/storage/core`). Each is a separate mount.
                                                     Root `/` filling is rare; a spec...
- **Database Bloat / Stats Table Growth**: The VPXD_HIST_STAT* tables, VPX_EVENT, and VPX_TASK
                                           tables grow without bound if retention settings are
                                           misconfigured or the purge job fails. vPostgres
                                           eventually runs out of disk or becomes critically slow.
- **vpxd Memory Exhaustion / Crash Loop**: Large inventories with many concurrent SDK sessions cause
                                           vpxd to exceed its heap. It crashes, vmon restarts it, it
                                           crashes again. During restarts, the inventory cache must
                                           be rebuilt from the database, which takes minutes to tens
                                           of minutes in large environments.
- **Service Dependency Deadlock**: A low-level service (STS, vPostgres, vmon) fails or is slow,
                                   causing cascading startup failures in dependent services. vmon
                                   may keep restarting services in the wrong order or give up after
                                   max retry attempts.
- **SSO/STS Token Validation Failures**: Separate from expiry. Clock skew, configuration drift in
                                         multi-vCenter topologies, or corrupted token signing
                                         certificates cause intermittent authentication failures
                                         that are maddening to diagnose.
- Any time the user reports a VMware vCenter Server Appliance (vCSA) service behaving outside its
  expected envelope (elevated errors, latency, saturation, resource exhaustion, or unexpected
  restarts).
- An on-call engineer is paging on a Netdata alert tied to a VMware vCenter Server Appliance (vCSA)
  instance and wants a structured triage path.

## Key facts

- This skill wraps the Netdata operator playbook for VMware vCenter Server Appliance (vCSA). It does
  not replace the playbook; it routes a coding agent through MCP queries against the same signals
  the playbook relies on.
- Dominant failure archetypes the playbook calls out: Certificate Expiry Cascade; Disk Space
  Exhaustion on a Specific Partition; Database Bloat / Stats Table Growth; vpxd Memory Exhaustion /
  Crash Loop; Service Dependency Deadlock.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your VMware vCenter Server Appliance (vCSA) instrumentation
  adds. Both paths end at the same MCP query surface.
- Netdata's vcsa collector emits 8 context(s) under `vcsa.*`. The rule files enumerate which
  contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the VMware vCenter Server Appliance (vCSA) service is up. Query Netdata via MCP with
   `list_nodes` and filter by the host running the target. A missing node means the symptom is at
   the network or orchestrator layer, not inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **Certificate Expiry Cascade**. The most devastating and most common. STS certificates,
   VMCA-signed machine certificates, or solution user certificates expire. Authentication fails.
   Services cannot communicate. The entire management plane goes dark. The insidious part: the
   certificates may have been valid for 2 years from initial deployment and nobody set calendar
   reminders. Inspect the rule file whose signals move first for this mode.
4. Check for **Disk Space Exhaustion on a Specific Partition**. vCSA has a non-obvious partition
   layout (`/storage/log`, `/storage/db`, `/storage/seat`, `/storage/updatemgr`, `/storage/netdump`,
   `/storage/autodeploy`, `/storage/imagebuilder`, `/storage/lifecycle`, `/storage/core`). Each is a
   separate mount. Root `/` filling is rare; a specific partition filling while root looks healthy
   is the norm. Inspect the rule file whose signals move first for this mode.
5. Check for **Database Bloat / Stats Table Growth**. The VPXD_HIST_STAT* tables, VPX_EVENT, and
   VPX_TASK tables grow without bound if retention settings are misconfigured or the purge job
   fails. vPostgres eventually runs out of disk or becomes critically slow. Inspect the rule file
   whose signals move first for this mode.
6. Check for **vpxd Memory Exhaustion / Crash Loop**. Large inventories with many concurrent SDK
   sessions cause vpxd to exceed its heap. It crashes, vmon restarts it, it crashes again. During
   restarts, the inventory cache must be rebuilt from the database, which takes minutes to tens of
   minutes in large environments. Inspect the rule file whose signals move first for this mode.
7. Check for **Service Dependency Deadlock**. A low-level service (STS, vPostgres, vmon) fails or is
   slow, causing cascading startup failures in dependent services. vmon may keep restarting services
   in the wrong order or give up after max retry attempts. Inspect the rule file whose signals move
   first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from VMware vCenter Server Appliance (vCSA)
list_metrics with q="vcsa"

# Pull a specific context over the last window
query_metrics with context="vcsa.system_health_status", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="vcsa.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating VMware vCenter Server Appliance (vCSA) as a generic HTTP or process health check. VMware
  vCenter Server Appliance (vCSA) has specific failure archetypes (see Key facts) that generic
  checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed VMware vCenter Server
  Appliance (vCSA) traffic before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the VMware vCenter Server Appliance
(vCSA) service. Every context listed below is a real Netdata chart name; the agent does not need to
guess.

```text
1. list_metrics filtered by q="vcsa" (returns every vcsa.* context Netdata sees)
2. query_metrics with contexts=[vcsa.system_health_status, vcsa.applmgmt_health_status, vcsa.load_health_status, vcsa.mem_health_status, vcsa.swap_health_status, vcsa.database_storage_health_status] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="vcsa.*"
```

Load-bearing contexts for this service:

- `vcsa.system_health_status`: VCSA Overall System health status (status). Dimensions: green, red,
                               yellow, orange, gray, unknown.
- `vcsa.applmgmt_health_status`: VCSA ApplMgmt health status (status). Dimensions: green, red,
                                 yellow, orange, gray, unknown.
- `vcsa.load_health_status`: VCSA Load health status (status). Dimensions: green, red, yellow,
                             orange, gray, unknown.
- `vcsa.mem_health_status`: VCSA Memory health status (status). Dimensions: green, red, yellow,
                            orange, gray, unknown.
- `vcsa.swap_health_status`: VCSA Swap health status (status). Dimensions: green, red, yellow,
                             orange, gray, unknown.
- `vcsa.database_storage_health_status`: VCSA Database Storage health status (status). Dimensions:
                                         green, red, yellow, orange, gray, unknown.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for VMware vCenter Server Appliance (vCSA):

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
