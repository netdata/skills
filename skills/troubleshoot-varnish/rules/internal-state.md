# Varnish Cache: Internal State signals

## Scope

Signals in the Internal State domain for Varnish Cache, as defined in the Netdata operator playbook. Each signal includes a short description, the collection source, and a hint for the MCP query pattern that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Ban List Growth [MEDIUM]

The size and growth rate of the ban list; invalidation rules checked during cache lookups.

Collection source: - `MAIN.bans`; current ban count (gauge) - `MAIN.bans_completed`; bans fully processed (gauge) - `MAIN.bans_lurker_obj_killed`; objects killed by ban lurker (counter) - `MAIN.bans_lurker_contention`; ban lurker yielded to lookups (counter) - `MAIN.bans_added`; bans added (counter) - `MAIN.bans_de...

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Object Count and Expiry [MEDIUM]

Current objects in cache and their expiry rate.

Collection source: - `MAIN.n_object`; current object count (gauge) - `MAIN.n_expired`; expired objects (counter)

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Request Coalescing Activity [LOW]

When multiple concurrent requests for the same uncached object wait for the first request to complete its backend fetch.

Collection source: - `MAIN.busy_sleep`; requests sent to sleep on busy objecthead (counter) - `MAIN.busy_wakeup`; requests woken after sleep (counter) - `MAIN.busy_killed`; requests killed on busy objecthead (counter, V6+)

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### VCL State [MEDIUM]

Tracking VCL load state and execution failures.

Collection source: - `MAIN.n_vcl`; loaded VCLs total (gauge) - `MAIN.n_vcl_avail`; VCLs available (gauge) - `MAIN.n_vcl_discard`; VCLs discarded (gauge) - `MAIN.vcl_fail`; VCL failures (counter, V6+)

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
find_anomalous_metrics filtered by any attribute unique to the Varnish Cache service (usually service.name or host.name)

# Look for correlated signals outside this domain
find_correlated_metrics around the incident window, limit 15
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
