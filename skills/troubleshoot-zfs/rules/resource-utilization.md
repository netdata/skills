# Zfs: Resource Utilization signals

## Scope

Signals in the Resource Utilization domain for Zfs, as defined in the Netdata operator playbook.
Each signal includes a short description, the collection source, and a hint for the MCP query
pattern that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### ARC Size and Hit Rate [MED]

Current size of the Adaptive Replacement Cache, its target maximum, and the ratio of reads served
from cache vs disk.

Collection source: `/proc/spl/kstat/zfs/arcstats`; key fields: - `size`: current ARC size in bytes -
`c`: current target size (dynamic, between c_min and c_max) - `c_max`: maximum ARC size target -
`c_min`: minimum ARC size - `hits`, `misses`: total cache hits/misses - `demand_data_hits`,
`demand_data_misses`: dema...

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Pool Capacity Utilization [MED]

Percentage of pool storage capacity currently allocated, including datasets, snapshots, and metadata
overhead.

Collection source: `zpool list`; CAP (capacity percentage), ALLOC, FREE columns. `zpool list -p`;
machine-parseable (bytes).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Dataset and Snapshot Space Distribution [MED]

Breakdown of pool space consumption by live data, snapshots, clones, and reservations. Identifies
the root cause of capacity problems.

Collection source: `zfs list -o space -r <pool>`; per-dataset breakdown with columns: NAME, AVAIL,
USED, USEDSNAP, USEDDS, USEDREFRESERV, USEDCHILD `zfs get -r usedbysnapshots <pool>`; snapshot space
per dataset `zpool get freeing <pool>`; bytes being asynchronously reclaimed

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Pool Fragmentation [MED]

Percentage of free-space fragmentation across metaslabs. Measures how scattered the available free
space is.

Collection source: `zpool list -o name,frag`; pool-level fragmentation `zpool list -v`; per-vdev
fragmentation

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

## Netdata contexts that surface Resource Utilization

These are the real Netdata chart contexts the native collector emits for Zfs. Use these names
verbatim in `query_metrics` calls.

- `zfspool.pool_space_utilization`: Zpool space utilization (%). Dimensions: utilization.
- `zfspool.pool_space_usage`: Zpool space usage (bytes). Dimensions: free, used.
- `zfspool.pool_fragmentation`: Zpool fragmentation (%). Dimensions: fragmentation.
- `zfspool.pool_health_state`: Zpool health state (state). Dimensions: online, degraded, faulted,
                               offline, unavail, removed.
- `zfspool.vdev_health_state`: Zpool Vdev health state (state). Dimensions: online, degraded,
                               faulted, offline, unavail, removed.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[zfspool.pool_space_utilization, zfspool.pool_space_usage, zfspool.pool_fragmentation, zfspool.pool_health_state, zfspool.vdev_health_state] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="zfspool.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="zfspool.pool_space_utilization"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
