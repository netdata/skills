# HAProxy: Errors signals

## Scope

Signals in the Errors domain for HAProxy, as defined in the Netdata operator playbook. Each signal includes a short description, the collection source, and a hint for the MCP query pattern that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### HTTP 5xx Response Rate [HIGH]

Count of HTTP responses with 5xx status codes. Cumulative counter; must compute deltas for rates.

Collection source: HAProxy stats CSV, field `hrsp_5xx` (index 42) on FRONTEND, BACKEND, and SERVER rows.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### HAProxy-Generated 5xx (Frontend − Backend Delta) [HIGH]

The difference between frontend `hrsp_5xx` and backend `hrsp_5xx` rates. This isolates errors HAProxy generated itself (503, 504) from errors the backend servers returned.

Collection source: Computed from HAProxy stats CSV: frontend `hrsp_5xx` rate minus sum of backend `hrsp_5xx` rates for that frontend's backends.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### HTTP 4xx Response Rate [MEDIUM]

Count of HTTP 4xx client error responses. Cumulative counter.

Collection source: HAProxy stats CSV, field `hrsp_4xx` (index 41).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Connection Errors (econ) [HIGH]

Count of errors when HAProxy attempts to connect to backend servers. Cumulative counter.

Collection source: HAProxy stats CSV, field `econ` (index 13) on BACKEND and SERVER rows.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Response Errors (eresp) [HIGH]

Count of response errors; the server sent an invalid or truncated response, or closed the connection mid-response. Cumulative counter.

Collection source: HAProxy stats CSV, field `eresp` (index 14) on BACKEND and SERVER rows.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Request Errors (ereq) [MEDIUM]

Count of request errors; malformed or protocol-violating client requests that HAProxy could not parse. Cumulative counter.

Collection source: HAProxy stats CSV, field `ereq` (index 12) on FRONTEND rows only.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Retries and Redispatches (wretr / wredis) [HIGH]

- `wretr`; count of connection retries to backend servers (HAProxy retried the same server after failure) - `wredis`; count of redispatches (HAProxy sent request to a different server than originally selected, after failure) Both cumulative counters.

Collection source: HAProxy stats CSV, fields `wretr` (index 15) and `wredis` (index 16) on BACKEND and SERVER rows.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Denied Requests / Denied Responses (dreq / dresp) [MEDIUM]

Count of requests denied by ACL rules (dreq) and responses denied by ACL rules (dresp). Cumulative counters.

Collection source: HAProxy stats CSV, fields `dreq` (index 10) on FRONTEND and BACKEND rows, `dresp` (index 11) on BACKEND and SERVER rows.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Client Aborts / Server Aborts (cli_abrt / srv_abrt) [MEDIUM]

- `cli_abrt`; count of transfers aborted by the client - `srv_abrt`; count of transfers aborted by the server Both cumulative counters.

Collection source: HAProxy stats CSV, fields `cli_abrt` (index 56) and `srv_abrt` (index 57) on BACKEND and SERVER rows.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Denied Connections / Denied Sessions (dcon / dses) [MEDIUM]

Connections and sessions rejected by TCP-level ACLs or connection limits. Cumulative counters.

Collection source: HAProxy stats CSV, fields `dcon` (index 84) and `dses` (index 85) on FRONTEND rows.

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
find_anomalous_metrics filtered by any attribute unique to the HAProxy service (usually service.name or host.name)

# Look for correlated signals outside this domain
find_correlated_metrics around the incident window, limit 15
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
