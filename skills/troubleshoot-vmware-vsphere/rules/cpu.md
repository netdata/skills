# VMware vSphere: Cpu signals

## Scope

Signals in the Cpu domain for VMware vSphere, as defined in the Netdata operator playbook. Each
signal includes a short description, the collection source, and a hint for the MCP query pattern
that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### CPU Ready Time (per VM) [HIGH]

The percentage of time a VM's vCPU was runnable (had work to do) but was waiting for a physical CPU
to become available. This is the single most important CPU signal in vSphere monitoring.

Collection source: ESXi performance counter: `cpu.ready.summation` (milliseconds per collection
interval). Must be converted to percentage: `(ready_ms / (interval_ms * num_vCPUs)) * 100`. esxtop:
%RDY column in CPU view.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### CPU Co-Stop (per VM) [HIGH]

The time a vCPU in a multi-vCPU VM is halted because the scheduler is waiting for other vCPUs to be
simultaneously co-scheduled. This is the scheduling tax for SMP VMs.

Collection source: ESXi performance counter: `cpu.costop.summation` (milliseconds). Convert to
percentage same as ready time. esxtop: %CSTP column per VM.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### CPU Max Limited (per VM) [HIGH]

Time a vCPU was runnable but not scheduled because the VM has hit its configured CPU limit (MHz
ceiling).

Collection source: ESXi performance counter: `cpu.maxlimited.summation` (milliseconds). esxtop:
%MLMTD column per VM.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Host CPU Utilization [HIGH]

Percentage of total physical CPU capacity consumed across all cores, including VMkernel overhead and
all VM worlds.

Collection source: ESXi performance counter: `cpu.usage.average` (percent, scaled 0-10000
representing 0-100.00%). esxtop: %USED column in PCPU section.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### NUMA Home Node Locality [MEDIUM]

The percentage of a VM's memory accesses satisfied by the local NUMA node versus remote nodes.

Collection source: ESXi performance counter: `numa.local` and `numa.remote` (memory access counts).
Locality % = local / (local + remote) * 100.

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

## Netdata contexts that surface Cpu

No Netdata-native contexts were classified into the Cpu domain for VMware vSphere. Use
discovery-style MCP calls below, or consult the full context list in SKILL.md.

## MCP query examples for this domain

```text
# Discover contexts for this service
list_metrics with q="vmware-vsphere"

# Rank anomalies on the host running this service
find_anomalous_metrics with node=<host>
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
