# VMware vSphere: Network signals

## Scope

Signals in the Network domain for VMware vSphere, as defined in the Netdata operator playbook. Each
signal includes a short description, the collection source, and a hint for the MCP query pattern
that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Dropped Packets (per vNIC and per pNIC) [HIGH]

Network packets dropped at the virtual switch port (vNIC side) or the physical NIC (uplink side).

Collection source: ESXi performance counters: `net.droppedRx.summation`, `net.droppedTx.summation`
per vNIC and pNIC. esxtop: %DRPTX, %DRPRX columns per port.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Physical Uplink Utilization [MEDIUM]

Bandwidth utilization on physical NICs (vmnics) that carry all traffic off the host.

Collection source: ESXi performance counters: `net.bytesRx.average` and `net.bytesTx.average` per
vmnic. esxtop: MbRX/s, MbTX/s for vmnic rows.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### vMotion Failure and Stun Time [MEDIUM]

vMotion migration failures and the stun time (brief pause) experienced by VMs during the final
switchover phase of live migration.

Collection source: vCenter events: `DrsVmMigratedEvent` (success), `VmFailedMigrateEvent` (failure).
vCenter API: Task completion status for migration operations.

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

## Netdata contexts that surface Network

These are the real Netdata chart contexts the native collector emits for VMware vSphere. Use these
names verbatim in `query_metrics` calls.

- `vsphere.vm_net_traffic`: Virtual Machine network traffic (KiB/s). Dimensions: received, sent.
- `vsphere.vm_net_packets`: Virtual Machine network packets (packets). Dimensions: received, sent.
- `vsphere.vm_net_drops`: Virtual Machine network dropped packets (packets). Dimensions: received,
                          sent.
- `vsphere.host_net_traffic`: ESXi Host network traffic (KiB/s). Dimensions: received, sent.
- `vsphere.host_net_packets`: ESXi Host network packets (packets). Dimensions: received, sent.
- `vsphere.host_net_drops`: ESXi Host network drops (packets). Dimensions: received, sent.
- `vsphere.host_net_errors`: ESXi Host network errors (errors). Dimensions: received, sent.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[vsphere.vm_net_traffic, vsphere.vm_net_packets, vsphere.vm_net_drops, vsphere.host_net_traffic, vsphere.host_net_packets, vsphere.host_net_drops] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="vsphere.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="vsphere.vm_net_traffic"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
