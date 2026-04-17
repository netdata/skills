# Apache Pulsar: Saturation & Resource Utilization signals

## Scope

Signals in the Saturation & Resource Utilization domain for Apache Pulsar, as defined in the Netdata operator playbook. Each signal includes a short description, the collection source, and a hint for the MCP query pattern that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Bookie Add Entry In-Progress Count [MED]

The number of add-entry operations currently in progress on a bookie; the write queue depth. This is the "pressure gauge" for the bookie write path.

Collection source: Bookie Prometheus metrics endpoint: `bookkeeper_server_ADD_ENTRY_IN_PROGRESS` (Gauge).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Managed Ledger Cache Efficiency [MED]

The hit/miss ratio and eviction rate of the broker's managed ledger cache; an off-heap memory region that caches recently written entries for fast consumer reads.

Collection source: Broker Prometheus metrics endpoint: - `pulsar_ml_cache_hits_rate` (Gauge, hits/sec) - `pulsar_ml_cache_misses_rate` (Gauge, misses/sec) - `pulsar_ml_cache_evictions` (Gauge, evictions in last minute) - `pulsar_ml_cache_used_size` (Gauge, bytes used)

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Broker Active Connection Count [MED]

Total number of active TCP connections on the broker (producers + consumers + internal connections).

Collection source: Broker Prometheus metrics endpoint: `pulsar_active_connections` (Gauge, labels: `{cluster, broker, metric}`).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Bookie Disk Usage [MED]

Percentage of disk space used on bookie ledger storage volumes. BookKeeper exposes per-directory usage.

Collection source: Bookie Prometheus metrics endpoint: `bookie_ledger_dir_{path}_usage` (Gauge, percentage 0-100) and `bookie_ledger_writable_dirs` (Gauge, count of writable directories).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Journal Force Write Queue Size [MED]

The depth of the queue of pending fsync operations on the bookie journal. This measures how many write batches are waiting to be durably committed to disk.

Collection source: Bookie Prometheus metrics endpoint: `bookie_journal_JOURNAL_FORCE_WRITE_QUEUE_SIZE` (Counter used as up/down gauge, `journalIndex` label).

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
find_anomalous_metrics filtered by any attribute unique to the Apache Pulsar service (usually service.name or host.name)

# Look for correlated signals outside this domain
find_correlated_metrics around the incident window, limit 15
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
