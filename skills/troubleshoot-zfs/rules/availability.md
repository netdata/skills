# Zfs: AVAILABILITY signals

## Scope

Signals in the AVAILABILITY domain for Zfs, as defined in the Netdata operator playbook. Each signal
includes a short description, the collection source, and a hint for the MCP query pattern that
surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Pool Health State [MED]

The aggregated health status of every vdev in the pool. Binary indicator of whether the pool can
service I/O requests.

Collection source: `zpool status` / `zpool list -H -o name,health` kstat:
`/proc/spl/kstat/zfs/<pool>/state` (single-line string: ONLINE, DEGRADED, FAULTED, SUSPENDED, etc.)

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Per-Vdev State and Error Counts (Data-Bearing Vdevs) [MED]

Individual data-bearing vdev (normal, special, dedup class) presence, state, and cumulative error
counters (READ errors, WRITE errors, CKSUM errors) within the pool hierarchy. Log (SLOG) and cache
(L2ARC) vdevs are covered separately.

Collection source: `zpool status -v`; shows vdev tree with state and error columns per device. Error
counters are cumulative since last `zpool clear`. They persist in-memory; reset by `zpool clear`,
and may also reset on pool export/import or module reload.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Scrub Status, Completion, and Permanent Errors [MED]

Whether integrity scrubs are running, completed successfully, found errors, or have not been run
recently. Also includes the permanent error list; files/objects with uncorrectable data loss.

Collection source: `zpool status`; the `scan:` line shows scrub state: - In progress: `scrub in
progress since <timestamp>` with bytes scanned, rate, bytes repaired, % done, ETA - Completed:
`scrub repaired <N>B in <elapsed> with <N> errors on <timestamp>` - No scrub: `none requested`

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
find_anomalous_metrics filtered by any attribute unique to the Zfs service (usually service.name or host.name)

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
