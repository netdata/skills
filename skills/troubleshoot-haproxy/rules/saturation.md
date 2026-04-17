# HAProxy: Saturation signals

## Scope

Signals in the Saturation domain for HAProxy, as defined in the Netdata operator playbook. Each
signal includes a short description, the collection source, and a hint for the MCP query pattern
that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Current Sessions vs Max Connections (scur / maxconn) [HIGH]

The current number of concurrent active sessions compared to the configured maximum (`maxconn`). The
primary saturation indicator.

Collection source: HAProxy stats CSV: `scur` (index 4, current sessions) and `slim` (index 6,
session limit/maxconn) on FRONTEND, BACKEND, and SERVER rows. Global: `CurrConns` and `Maxconn` in
`show info`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Backend Queue Depth (qcur) [HIGH]

The number of connections currently waiting in the backend's queue because no server had an
available connection slot.

Collection source: HAProxy stats CSV, field `qcur` (index 2) on BACKEND and SERVER rows.
Instantaneous gauge.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Idle Percentage (Idle_pct) [HIGH]

The percentage of time the HAProxy event loop spends idle (waiting in `poll()`) vs. doing actual
work. 100% = fully idle, near 0% = event loop saturated.

Collection source: `show info` field `Idle_pct`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### File Descriptor Headroom [HIGH]

The gap between currently used file descriptors and the process FD limit (`ulimit -n`). FD
exhaustion is a hard cliff; `accept()` fails immediately with no graceful degradation.

Collection source: `show info` fields `Maxsock` (configured FD limit for HAProxy) and `CurrConns`
(approximate FD usage via connection count × 2 + overhead). System-level: `/proc/<pid>/fd` count vs
`/proc/<pid>/limits`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Memory Allocator Pressure (PoolFailed) [MEDIUM]

Count of failed memory pool allocations within HAProxy's internal allocator.

Collection source: `show info` field `PoolFailed`. Also: `show pools` command shows per-pool
allocation statistics.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Connection Pool Utilization [MEDIUM]

The ratio of reused backend connections vs. new connections. Indicates how effectively HAProxy
avoids TCP/TLS handshake overhead.

Collection source: HAProxy stats CSV, fields `connect` (index 78) and `reuse` (index 79) on BACKEND
and SERVER rows (cumulative counters). Server-level gauges: `idle_conn_cur` (index 80),
`safe_conn_cur` (index 81), `used_conn_cur` (index 82), `need_conn_est` (index 83).

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
find_anomalous_metrics filtered by any attribute unique to the HAProxy service (usually service.name or host.name)

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
