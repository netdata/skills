# VMware vSphere: Hardware & Host Health signals

## Scope

Signals in the Hardware & Host Health domain for VMware vSphere, as defined in the Netdata operator
playbook. Each signal includes a short description, the collection source, and a hint for the MCP
query pattern that surfaces it. Use this file during a triage pass to decide which signal to pull
first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### ESXi Host Hardware Health [HIGH]

Physical hardware sensor readings: CPU temperature, fan speed, power supply status, memory DIMM
errors, disk predictive failure.

Collection source: ESXi CIM providers, IPMI/BMC (iLO, iDRAC, IMM). esxcli: `esxcli hardware platform
get`, `esxcli hardware memory get`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Storage Path Health [MEDIUM]

Status and error count on storage paths between ESXi hosts and storage arrays.

Collection source: ESXi: `esxcli storage core path list`, `/var/log/vmkernel.log`. esxtop: ERR/s
column in storage view.

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

## Netdata contexts that surface Hardware & Host Health

These are the real Netdata chart contexts the native collector emits for VMware vSphere. Use these
names verbatim in `query_metrics` calls.

- `vsphere.host_cpu_utilization`: ESXi Host CPU utilization (percentage). Dimensions: used.
- `vsphere.host_mem_utilization`: ESXi Host memory utilization (percentage). Dimensions: used.
- `vsphere.host_mem_usage`: ESXi Host memory usage (KiB). Dimensions: granted, consumed, active,
                            shared, sharedcommon.
- `vsphere.host_mem_swap_io`: ESXi Host VMKernel memory swap IO (KiB/s). Dimensions: in, out.
- `vsphere.host_disk_io`: ESXi Host disk IO (KiB/s). Dimensions: read, write.
- `vsphere.host_disk_max_latency`: ESXi Host disk max latency (milliseconds). Dimensions: latency.
- `vsphere.host_net_traffic`: ESXi Host network traffic (KiB/s). Dimensions: received, sent.
- `vsphere.host_net_packets`: ESXi Host network packets (packets). Dimensions: received, sent.
- `vsphere.host_net_drops`: ESXi Host network drops (packets). Dimensions: received, sent.
- `vsphere.host_net_errors`: ESXi Host network errors (errors). Dimensions: received, sent.
- `vsphere.host_overall_status`: ESXi Host overall alarm status (status). Dimensions: green, red,
                                 yellow, gray.
- `vsphere.host_system_uptime`: ESXi Host system uptime (seconds). Dimensions: uptime.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[vsphere.host_cpu_utilization, vsphere.host_mem_utilization, vsphere.host_mem_usage, vsphere.host_mem_swap_io, vsphere.host_disk_io, vsphere.host_disk_max_latency] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="vsphere.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="vsphere.host_cpu_utilization"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
