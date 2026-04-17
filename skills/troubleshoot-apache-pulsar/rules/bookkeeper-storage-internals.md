# Apache Pulsar: Bookkeeper Storage Internals signals

## Scope

Signals in the Bookkeeper Storage Internals domain for Apache Pulsar, as defined in the Netdata
operator playbook. Each signal includes a short description, the collection source, and a hint for
the MCP query pattern that surfaces it. Use this file during a triage pass to decide which signal to
pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Bookie Read Latency [MED]

The latency of read operations on bookies; how long it takes to retrieve a ledger entry from disk or
cache.

Collection source: Bookie Prometheus metrics endpoint: - `bookkeeper_server_READ_ENTRY_REQUEST`
(Summary, end-to-end read request latency) - `bookie_BOOKIE_READ_ENTRY` (Summary, bookie-level read
latency; the actual disk/cache operation)

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Bookie Write Cache and Read Cache Hit Rates [MED]

The hit/miss ratio of the bookie-level caches (DbLedgerStorage backend, which is Pulsar's default).
Write cache holds recently written entries; read cache holds recently read entries.

Collection source: Bookie Prometheus metrics endpoint (DbLedgerStorage): - `bookie_write_cache_hits`
/ `bookie_write_cache_misses` (Counters) - `bookie_read_cache_hits` / `bookie_read_cache_misses`
(Counters)

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Active Entry Log Count and Space [MED]

The number and total size of active (non-garbage-collected) entry log files on a bookie. Entry logs
contain the actual message data interleaved across ledgers.

Collection source: Bookie Prometheus metrics endpoint: - `bookie_ACTIVE_ENTRY_LOG_TOTAL` (Gauge,
count of active entry log files) - `bookie_ACTIVE_ENTRY_LOG_SPACE_BYTES` (Gauge, total bytes in
active entry logs) - `bookie_ENTRY_LOG_SPACE_BYTES` (Gauge, total bytes across all entry log files)

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
find_anomalous_metrics filtered by any attribute unique to the Apache Pulsar service (usually service.name or host.name)

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
