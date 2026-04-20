# VMware vSphere: Storage signals

## Scope

Signals in the Storage domain for VMware vSphere, as defined in the Netdata operator playbook. Each
signal includes a short description, the collection source, and a hint for the MCP query pattern
that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Datastore Latency; DAVG, KAVG, GAVG [HIGH]

Three latency measurements along the storage I/O path: - **GAVG** (Guest Average): Total latency as
seen by the VM = KAVG + DAVG + queue time. - **KAVG** (Kernel Average): Latency added by the
VMkernel (queuing, virtualization overhead). - **DAVG** (Device Average): Latency at the physical
storage device; the array response time.

Collection source: ESXi performance counters: - `disk.totalLatency.average` (per device) ≈ GAVG -
`disk.kernelLatency.average` (per device) = KAVG - `disk.deviceLatency.average` (per device) = DAVG
- Per-VM: `virtualDisk.totalReadLatency.average` and `virtualDisk.totalWriteLatency.average`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Outstanding I/Os (Queue Depth) [HIGH]

Number of I/O operations in flight; queued or in-progress; between the VMkernel and storage device.

Collection source: esxtop: ACTV (active I/Os at device), QUED (queued in VMkernel) per device.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Datastore Free Space [HIGH]

Available free space on a VMFS or NFS datastore.

Collection source: ESXi CLI: `esxcli storage filesystem list`; shows mount point, type, size, free
space. vCenter API: `Datastore.summary.capacity` and `Datastore.summary.freeSpace`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Snapshot Age and Chain Depth [HIGH]

The number of snapshots in each VM's chain and how long they have been active.

Collection source: vCenter API: `VirtualMachine.snapshot` property; snapshot tree per VM. Not
exposed as a performance counter. Must be queried via API or PowerCLI.

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

## Netdata contexts that surface Storage

These are the real Netdata chart contexts the native collector emits for VMware vSphere. Use these
names verbatim in `query_metrics` calls.

- `vsphere.vm_cpu_utilization`: Virtual Machine CPU utilization (percentage). Dimensions: used.
- `vsphere.vm_mem_utilization`: Virtual Machine memory utilization (percentage). Dimensions: used.
- `vsphere.vm_mem_swap_io`: Virtual Machine VMKernel memory swap IO (KiB/s). Dimensions: in, out.
- `vsphere.vm_disk_io`: Virtual Machine disk IO (KiB/s). Dimensions: read, write.
- `vsphere.vm_disk_max_latency`: Virtual Machine disk max latency (milliseconds). Dimensions:
                                 latency.
- `vsphere.host_cpu_utilization`: ESXi Host CPU utilization (percentage). Dimensions: used.
- `vsphere.host_mem_utilization`: ESXi Host memory utilization (percentage). Dimensions: used.
- `vsphere.host_mem_swap_io`: ESXi Host VMKernel memory swap IO (KiB/s). Dimensions: in, out.
- `vsphere.host_disk_io`: ESXi Host disk IO (KiB/s). Dimensions: read, write.
- `vsphere.host_disk_max_latency`: ESXi Host disk max latency (milliseconds). Dimensions: latency.
- `vsphere.datastore_disk_io`: Datastore disk IO (KiB/s). Dimensions: read, write.
- `vsphere.datastore_disk_iops`: Datastore disk IOPS (operations/s). Dimensions: reads, writes.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[vsphere.vm_cpu_utilization, vsphere.vm_mem_utilization, vsphere.vm_mem_swap_io, vsphere.vm_disk_io, vsphere.vm_disk_max_latency, vsphere.host_cpu_utilization] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="vsphere.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="vsphere.vm_cpu_utilization"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
