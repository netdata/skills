# LVM (Linux Logical Volume Manager): Saturation Domain signals

## Scope

Signals in the Saturation Domain domain for LVM (Linux Logical Volume Manager), as defined in the
Netdata operator playbook. Each signal includes a short description, the collection source, and a
hint for the MCP query pattern that surfaces it. Use this file during a triage pass to decide which
signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Volume Group Free Space [HIGH]

The number and percentage of unallocated Physical Extents remaining in a VG; the headroom for
creating or extending LVs, creating snapshots, and auto-extending thin pools.

Collection source: `vgs` command output (`vg_free`, `vg_free_count`, `vg_extent_count`). VG metadata
on disk.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Thin Pool Data Usage [HIGH]

The percentage of physical storage consumed by all thin volumes within a thin pool. This is the
`data_percent` field; the ratio of used data blocks to total data blocks in the pool.

Collection source: `lvs` command with `data_percent` field. Device-mapper status via `dmsetup status
<vg>-<thinpool>` (output includes `used_data_blocks/total_data_blocks`).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Thin Pool Metadata Usage [HIGH]

The percentage of metadata space used in the thin pool's internal metadata LV. This metadata tracks
the block mapping table for all thin volumes. The `metadata_percent` field.

Collection source: `lvs` command with `metadata_percent` field. `dmsetup status` output includes
`used_metadata_blocks/total_metadata_blocks`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Snapshot Usage (Traditional COW Snapshots) [HIGH]

The percentage of the COW exception store consumed for each traditional (non-thin) snapshot. The
`snap_percent` field.

Collection source: `lvs` command with `snap_percent` and `origin` fields. Device-mapper status for
snapshot devices.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### LV Health Status [HIGH]

The health indicator from `lv_attr` position 9, revealing structural problems with logical volumes.

Collection source: `lvs` command, `lv_attr` field, position 9 (the 9th character).

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

## MCP query examples for this domain

```text
# Pull every signal in this domain at once
query_metrics with contexts=[<signals from the list above>] and relative_window=-30m

# Ask the agent to rank anomalies that match this domain
find_anomalous_metrics filtered by any attribute unique to the LVM (Linux Logical Volume Manager) service (usually service.name or host.name)

# Look for correlated signals outside this domain
find_correlated_metrics around the incident window, limit 15
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
