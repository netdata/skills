---
name: troubleshoot-vmware-vsphere
description: "Use when diagnosing issues with VMware vSphere: cpu starvation, memory pressure cascade, storage latency cliff, numa penalty, or snapshot accumulation. Queries Netdata via MCP for cpu ready time (per vm), cpu co-stop (per vm), memory balloon (per vm and host), host swap activity (vmkernel-level swap), datastore latency; davg, kavg, gavg, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - vmware-vsphere
---

# Troubleshoot VMware vSphere

## When to use this skill

- **CPU starvation**: VMs have sufficient vCPUs but insufficient pCPU time. Manifests as high ready
                      time and co-stop. Guest CPU utilization appears low because the guest doesn't
                      know it's being descheduled.
- **Memory pressure cascade**: Ballooning starts (moderate), then compression (noticeable), then
                               swapping (catastrophic). Can happen in minutes during workload
                               spikes.
- **Storage latency cliff**: Queue saturation or array-side slowdown. Latency jumps from <5ms to
                             50-500ms. VMs appear to freeze. The #1 cause of "everything is slow"
                             incidents.
- **NUMA penalty**: Large VMs spanning NUMA nodes silently lose 10-30% memory throughput.
- **Snapshot accumulation**: Snapshots left for days/weeks. Delta VMDK grows until datastore fills.
                             Consolidation stuns the VM.
- **vCenter database bloat**: Statistics, events, tasks accumulate. PostgreSQL bloats. vpxd slows.
                              Eventually vCenter becomes unresponsive, and DRS/HA stop functioning.
- Any time the user reports a VMware vSphere service behaving outside its expected envelope
  (elevated errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a VMware vSphere instance and wants a
  structured triage path.

## Key facts

- This skill wraps the Netdata operator playbook for VMware vSphere. It does not replace the
  playbook; it routes a coding agent through MCP queries against the same signals the playbook
  relies on.
- vSphere is a layered virtualization stack with three interdependent planes that must be understood
  together to reason about failures.
- The playbook decomposes VMware vSphere health into 8 signal domains: Cpu, Memory, Storage,
  Network, Availability & Vcenter Services, Hardware & Host Health. Each domain maps to one rule
  file in this skill.
- Dominant failure archetypes the playbook calls out: CPU starvation; Memory pressure cascade;
  Storage latency cliff; NUMA penalty; Snapshot accumulation.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your VMware vSphere instrumentation adds. Both paths end at the
  same MCP query surface.
- Netdata's vsphere collector emits 66 context(s) under `vsphere.*`. The rule files enumerate which
  contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the VMware vSphere service is up. Query Netdata via MCP with `list_nodes` and filter by
   the host running the target. A missing node means the symptom is at the network or orchestrator
   layer, not inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **CPU starvation**. VMs have sufficient vCPUs but insufficient pCPU time. Manifests as
   high ready time and co-stop. Guest CPU utilization appears low because the guest doesn't know
   it's being descheduled. Inspect the rule file whose signals move first for this mode.
4. Check for **Memory pressure cascade**. Ballooning starts (moderate), then compression
   (noticeable), then swapping (catastrophic). Can happen in minutes during workload spikes. Inspect
   the rule file whose signals move first for this mode.
5. Check for **Storage latency cliff**. Queue saturation or array-side slowdown. Latency jumps from
   <5ms to 50-500ms. VMs appear to freeze. The #1 cause of "everything is slow" incidents. Inspect
   the rule file whose signals move first for this mode.
6. Check for **NUMA penalty**. Large VMs spanning NUMA nodes silently lose 10-30% memory throughput.
   Inspect the rule file whose signals move first for this mode.
7. Check for **Snapshot accumulation**. Snapshots left for days/weeks. Delta VMDK grows until
   datastore fills. Consolidation stuns the VM. Inspect the rule file whose signals move first for
   this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from VMware vSphere
list_metrics with q="vsphere"

# Pull a specific context over the last window
query_metrics with context="vsphere.vm_overall_status", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="vsphere.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating VMware vSphere as a generic HTTP or process health check. VMware vSphere has specific
  failure archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed VMware vSphere
  traffic before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the VMware vSphere service. Every
context listed below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="vsphere" (returns every vsphere.* context Netdata sees)
2. query_metrics with contexts=[vsphere.vm_overall_status, vsphere.vm_system_uptime, vsphere.host_overall_status, vsphere.host_system_uptime, vsphere.datastore_overall_status, vsphere.cluster_overall_status] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="vsphere.*"
```

Load-bearing contexts for this service:

- `vsphere.vm_overall_status`: Virtual Machine overall alarm status (status). Dimensions: green,
                               red, yellow, gray.
- `vsphere.vm_system_uptime`: Virtual Machine system uptime (seconds). Dimensions: uptime.
- `vsphere.host_overall_status`: ESXi Host overall alarm status (status). Dimensions: green, red,
                                 yellow, gray.
- `vsphere.host_system_uptime`: ESXi Host system uptime (seconds). Dimensions: uptime.
- `vsphere.datastore_overall_status`: Datastore overall alarm status (status). Dimensions: green,
                                      red, yellow, gray.
- `vsphere.cluster_overall_status`: Cluster overall alarm status (status). Dimensions: green, red,
                                    yellow, gray.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for VMware vSphere:

- Host-resource pressure masquerading as application bug.
- Dependent service (DB, cache, upstream) causing a secondary symptom in the instrumented service.
- Configuration change that was never reloaded (some subsystems only pick up config on full
  restart).

Escalate by widening the query window: 2-6 hours instead of 15 minutes. Slow-moving causes are
invisible at triage window sizes.

## References

- [`rules/cpu.md`](./rules/cpu.md)
- [`rules/memory.md`](./rules/memory.md)
- [`rules/storage.md`](./rules/storage.md)
- [`rules/network.md`](./rules/network.md)
- [`rules/availability-vcenter-services.md`](./rules/availability-vcenter-services.md)
- [`rules/hardware-host-health.md`](./rules/hardware-host-health.md)
- [`rules/security-integrity.md`](./rules/security-integrity.md)
- [`rules/additional-operational-signals.md`](./rules/additional-operational-signals.md)
- Netdata operator playbook: the authoritative source material this skill summarizes.
- `skills/netdata-mcp-integration/` for the transport setup.
- `skills/netdata-otel-setup/` if additional application signals are needed beyond what Netdata
  collects natively.
