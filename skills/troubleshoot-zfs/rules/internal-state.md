# Zfs: INTERNAL STATE signals

## Scope

Signals in the INTERNAL STATE domain for Zfs, as defined in the Netdata operator playbook. Each signal includes a short description, the collection source, and a hint for the MCP query pattern that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Transaction Group (TXG) Sync Duration [MED]

Time taken to commit each transaction group to stable storage.

Collection source: `/proc/spl/kstat/zfs/<pool>/txgs`; TXG history. Format: `txg birth state ndirty nread nwritten reads writes otime qtime wtime stime` - `stime`: sync phase duration in nanoseconds (the critical metric) - `ndirty`: dirty bytes in this TXG

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Dirty Data and Writer Throttling [MED]

The amount of dirty (uncommitted) data accumulated in memory, and whether ZFS is actively throttling write operations to prevent memory exhaustion.

Collection source: `/proc/spl/kstat/zfs/<pool>/txgs`; `ndirty` field (dirty bytes per TXG) `/sys/module/zfs/parameters/zfs_dirty_data_max`; configured maximum dirty data limit `/sys/module/zfs/parameters/zfs_delay_min_dirty_percent`; threshold (default 60%) at which ZFS starts throttling writers

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### ZFS Deadman Events [MED]

Alerts from ZFS's internal "deadman" subsystem that detects hung I/O operations or stalled pool sync.

Collection source: `zpool events`; `FM_EREPORT_ZFS_DEADMAN` events Tunables in `/sys/module/zfs/parameters/`: - `zfs_deadman_enabled` (default: 1) - `zfs_deadman_synctime_ms` (default: 600000 = 10 minutes) - `zfs_deadman_ziotime_ms` (default: 300000 = 5 minutes) - `zfs_deadman_failmode` (default: "wait")

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### ZIL Commit Activity [MED]

Counters tracking synchronous write (ZIL) commit operations.

Collection source: `/proc/spl/kstat/zfs/zil`; global ZIL statistics: - `zil_commit_count`: total commits requested - `zil_commit_writer_count`: times ZIL actually wrote - `zil_commit_error_count`: commit errors - `zil_commit_stall_count`: commit stalls - `zil_itx_count`, `zil_itx_indirect_count`, `zil_itx_copied_co...

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### SLOG/L2ARC Device Health [MED]

Status of dedicated cache (L2ARC) and log (SLOG) devices.

Collection source: `zpool status -v`; cache and log vdev state and error counts. L2ARC stats: `l2_hits`, `l2_misses`, `l2_read_bytes`, `l2_write_bytes`, `l2_io_error` in `/proc/spl/kstat/zfs/arcstats`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Resilver Status and Progress [MED]

Current status of vdev reconstruction after device replacement or fault.

Collection source: `zpool status`; `scan:` line for resilver.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Dedup DDT Memory Pressure (Variant-Specific) [MED]

Memory consumption by the Deduplication Table (DDT) when dedup is enabled. Only relevant for pools with `dedup=on`.

Collection source: `zpool status -D <pool>`; DDT statistics `zdb -S <pool>`; DDT size analysis `/proc/spl/kstat/zfs/arcstats`; `ddt_size` if available in ARC metadata breakdown

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

## Triage order within this domain

Investigate HIGH-severity signals first, then MEDIUM, then LOW. HIGH-severity signals have the shortest time to impact; a confirmed HIGH anomaly usually justifies paging. When two HIGH signals move together, treat them as one incident until `find_correlated_metrics` rules out shared cause.

## Common false positives

- A single stale data point from a collector restart triggers many signals briefly. Re-query after 30 seconds before escalating.
- Short bursts under 60 seconds rarely warrant action unless paired with a confirmed business impact.
- Comparing against yesterday's baseline on a post-deploy day produces false anomalies. Compare against the pre-deploy baseline.
- Collector-visible percentile latency with < 100 samples per minute is noise. Require a minimum sample count before acting.

## Remediation pointers

Remediation for signals in this domain is tech-specific and typically covered in the operator playbook's SECTION 3 (Failure Patterns) or SECTION 4 (Runbooks). Before applying a change:

1. Run the MCP verification queries to record the current state.
2. Apply the smallest remediation that addresses the confirmed cause. Config changes before restarts; restarts before rollbacks.
3. Re-run the same MCP queries after the remediation settles. Recording before/after numbers is how a runbook entry gets sharpened over time.

## MCP query examples for this domain

```text
# Pull every signal in this domain at once
query_metrics with contexts=[<signals from the list above>] and relative_window=-30m

# Ask the agent to rank anomalies that match this domain
find_anomalous_metrics filtered by any attribute unique to the Zfs service (usually service.name or host.name)

# Look for correlated signals outside this domain
find_correlated_metrics around the incident window, limit 15
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
