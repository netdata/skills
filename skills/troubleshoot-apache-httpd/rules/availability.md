# Apache HTTPD: Availability signals

## Scope

Signals in the Availability domain for Apache HTTPD, as defined in the Netdata operator playbook.
Each signal includes a short description, the collection source, and a hint for the MCP query
pattern that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Process Presence [HIGH]

Whether the Apache parent process exists.

Collection source: - PID file: `/var/run/apache2/apache2.pid` (Debian) or `/var/run/httpd/httpd.pid`
(RHEL) - Process table: `pgrep -o httpd` or `pgrep -o apache2` (oldest = parent)

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Critical-Path Reachability [HIGH]

Whether the service responds to an HTTP request on the actual critical path (not just TCP port
check).

Collection source: - HTTP probe to the primary service URL (e.g., health endpoint, main vhost) - TCP
listener check as fallback

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Configuration Reload Success [MEDIUM]

Whether the last graceful reload successfully applied the new configuration.

Collection source: - Error log: messages between "resuming normal operations" entries - `apachectl
configtest` exit code

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

## Netdata contexts that surface Availability

These are the real Netdata chart contexts the native collector emits for Apache HTTPD. Use these
names verbatim in `query_metrics` calls.

- `apache.connections`: Connections (connections). Dimensions: connections.
- `apache.conns_async`: Active Connections (connections). Dimensions: keepalive, closing, writing.
- `apache.scoreboard`: Scoreboard (connections). Dimensions: waiting, starting, reading, sending,
                       keepalive, dns_lookup.
- `apache.uptime`: Uptime (seconds). Dimensions: uptime.
- `apache.connections`: Connections (connections). Dimensions: connections.
- `apache.conns_async`: Active Connections (connections). Dimensions: keepalive, closing, writing.
- `apache.scoreboard`: Scoreboard (connections). Dimensions: waiting, starting, reading, sending,
                       keepalive, dns_lookup.
- `apache.uptime`: Uptime (seconds). Dimensions: uptime.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[apache.connections, apache.conns_async, apache.scoreboard, apache.uptime, apache.connections, apache.conns_async] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="apache.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="apache.connections"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
