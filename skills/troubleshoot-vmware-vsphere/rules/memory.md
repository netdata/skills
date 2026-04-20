# VMware vSphere: Memory signals

## Scope

Signals in the Memory domain for VMware vSphere, as defined in the Netdata operator playbook. Each
signal includes a short description, the collection source, and a hint for the MCP query pattern
that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Memory Balloon (per VM and Host) [HIGH]

Amount of memory being reclaimed from a VM by inflating the balloon driver (vmmemctl) inside the
guest, forcing the guest to page internally.

Collection source: ESXi performance counter: `mem.vmmemctl.average` (KB); current balloon size per
VM. esxtop: MCTLSZ (balloon current size) and MCTLTGT (balloon target) per VM.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Host Swap Activity (VMkernel-level swap) [HIGH]

The rate at which the VMkernel swaps VM memory pages to/from .vswp files on the datastore. This is
the last-resort memory reclamation mechanism.

Collection source: ESXi performance counters: `mem.swapinRate.average` and `mem.swapoutRate.average`
(KBps). `mem.swapped.average` (KB; total currently swapped). esxtop: SWCUR (current swap used),
SWR/s (swap read rate), SWW/s (swap write rate) per VM.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Memory Compression Rate [MEDIUM]

Rate at which the VMkernel compresses memory pages into the compression cache instead of swapping to
disk.

Collection source: ESXi performance counters: `mem.compressionRate.average` (KBps),
`mem.decompressionRate.average` (KBps), `mem.compressed.average` (KB total). esxtop: ZIP/s
(compression rate) and UNZIP/s (decompression rate) per VM.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

## Triage order within this domain

Investigate HIGH-severity signals first, then MEDIUM, then LOW. HIGH-severity signals have the
shortest time to impact; a confirmed HIGH anomaly usually justifies paging. When two HIGH signals
move together, treat them as one incident until `find_correlated_metrics` rules out shared cause.

## Common false positives

- A single stale data point from a collector restart triggers many signals briefly. Re-query after
  30 seconds before escalating.
- Short bursts under 60 seconds rarely warrant action unless paired with a confirmed business
  impact.
- Comparing against yesterday's baseline on a post-deploy day produces false anomalies. Compare
  against the pre-deploy baseline.
- Collector-visible percentile latency with < 100 samples per minute is noise. Require a minimum
  sample count before acting.

## Remediation pointers

Remediation for signals in this domain is tech-specific and typically covered in the operator
playbook's SECTION 3 (Failure Patterns) or SECTION 4 (Runbooks). Before applying a change:

1. Run the MCP verification queries to record the current state.
2. Apply the smallest remediation that addresses the confirmed cause. Config changes before
   restarts; restarts before rollbacks.
3. Re-run the same MCP queries after the remediation settles. Recording before/after numbers is how
   a runbook entry gets sharpened over time.

## Netdata contexts that surface Memory

These are the real Netdata chart contexts the native collector emits for VMware vSphere. Use these
names verbatim in `query_metrics` calls.

- `vsphere.vm_mem_utilization`: Virtual Machine memory utilization (percentage). Dimensions: used.
- `vsphere.vm_mem_usage`: Virtual Machine memory usage (KiB). Dimensions: granted, consumed, active,
                          shared.
- `vsphere.vm_mem_swap_usage`: Virtual Machine VMKernel memory swap usage (KiB). Dimensions:
                               swapped.
- `vsphere.vm_mem_swap_io`: Virtual Machine VMKernel memory swap IO (KiB/s). Dimensions: in, out.
- `vsphere.host_mem_utilization`: ESXi Host memory utilization (percentage). Dimensions: used.
- `vsphere.host_mem_usage`: ESXi Host memory usage (KiB). Dimensions: granted, consumed, active,
                            shared, sharedcommon.
- `vsphere.host_mem_swap_io`: ESXi Host VMKernel memory swap IO (KiB/s). Dimensions: in, out.
- `vsphere.cluster_mem_capacity`: Cluster memory capacity (bytes). Dimensions: total, effective.
- `vsphere.cluster_usage_mem`: Cluster DRS memory usage summary (MB). Dimensions: demand, entitled,
                               reserved.
- `vsphere.cluster_mem_utilization`: Cluster memory utilization (percentage). Dimensions: used.
- `vsphere.cluster_mem_usage`: Cluster memory usage (KiB). Dimensions: consumed, active, granted,
                               shared, overhead, swap_used.
- `vsphere.cluster_services_fairness`: Cluster DRS resource distribution fairness (score).
                                       Dimensions: cpu, memory.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[vsphere.vm_mem_utilization, vsphere.vm_mem_usage, vsphere.vm_mem_swap_usage, vsphere.vm_mem_swap_io, vsphere.host_mem_utilization, vsphere.host_mem_usage] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="vsphere.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="vsphere.vm_mem_utilization"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
