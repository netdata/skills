# Envoy: Errors signals

## Scope

Signals in the Errors domain for Envoy, as defined in the Netdata operator playbook. Each signal includes a short description, the collection source, and a hint for the MCP query pattern that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Upstream Error Rate (5xx) [HIGH]

The rate of 5xx responses returned through upstream clusters. NOTE: This includes BOTH responses forwarded from the upstream service AND 5xx responses generated locally by Envoy (e.g., 503 from circuit breaker, 504 from timeout). Cluster-level dynamic HTTP stats count the final response code sent downstream, regardless of origin.

Collection source: Stats (dynamic HTTP): `cluster.<name>.upstream_rq_5xx` (counter, aggregate), `cluster.<name>.upstream_rq_503` (counter, specific). Also: `http.<stat_prefix>.downstream_rq_5xx` for total 5xx seen by clients.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Response Flags (Access Log Analysis) [HIGH]

Envoy attaches internal response flags to every request indicating the precise reason the response was generated or modified. These are the most powerful debugging signal Envoy provides; they separate "what happened" (5xx) from "why it happened" (circuit breaker, no route, upstream failure, etc.).

Collection source: Access logs: the `%RESPONSE_FLAGS%` field. NOTE: Response flags are access-log only; they are NOT exposed as aggregate Prometheus stats. To monitor them, you need access log processing (e.g., log pipeline with counters) or custom stats via Lua/Wasm filters.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Upstream Connection Failures [HIGH]

The count of failed TCP connection attempts to upstream hosts.

Collection source: Stat: `cluster.<name>.upstream_cx_connect_fail` (counter).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Upstream Request Failures [HIGH]

Breakdown of upstream request failures by cause: timeout, reset (local/remote), cancellation, maintenance mode.

Collection source: Stats: `cluster.<name>.upstream_rq_timeout` (counter), `upstream_rq_per_try_timeout` (counter), `upstream_rq_rx_reset` (counter), `upstream_rq_tx_reset` (counter), `upstream_rq_cancelled` (counter), `upstream_rq_maintenance_mode` (counter), `upstream_rq_max_duration_reached` (counter).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Downstream Connection Rejections [HIGH]

Connections rejected at the listener level due to overflow, overload, or global limits.

Collection source: Stats: `listener.<address>.downstream_cx_overflow` (counter), `listener.<address>.downstream_cx_overload_reject` (counter), `listener.<address>.downstream_global_cx_overflow` (counter).

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
find_anomalous_metrics filtered by any attribute unique to the Envoy service (usually service.name or host.name)

# Look for correlated signals outside this domain
find_correlated_metrics around the incident window, limit 15
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
