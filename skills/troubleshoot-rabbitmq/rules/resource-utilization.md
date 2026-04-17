# RabbitMQ: Resource Utilization signals

## Scope

Signals in the Resource Utilization domain for RabbitMQ, as defined in the Netdata operator
playbook. Each signal includes a short description, the collection source, and a hint for the MCP
query pattern that surfaces it. Use this file during a triage pass to decide which signal to pull
first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Memory Usage [HIGH]

The amount of memory currently used by the RabbitMQ node, compared to the configured memory limit
(`mem_limit`).

Collection source: - HTTP Management API: `GET /api/nodes`; fields `mem_used` (bytes), `mem_limit`
(bytes) - Note: `mem_limit` is the effective memory limit; it already incorporates the
`vm_memory_high_watermark` setting applied to total RAM. Do NOT multiply `mem_limit` by the
watermark again.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### File Descriptor Usage [HIGH]

The number of file descriptors currently in use by the RabbitMQ Erlang node vs the configured total
limit.

Collection source: - HTTP Management API: `GET /api/nodes`; fields `fd_used`, `fd_total`

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Socket Usage [HIGH]

The number of network sockets (a subset of file descriptors) used by the RabbitMQ node vs the socket
limit.

Collection source: - HTTP Management API: `GET /api/nodes`; fields `sockets_used`, `sockets_total` -
Note: Socket metrics are available only via the Management API, not via the Prometheus plugin.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Erlang Process Usage [MEDIUM]

The number of Erlang processes currently running in the VM vs the configured process limit.

Collection source: - HTTP Management API: `GET /api/nodes`; fields `proc_used`, `proc_total`

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Disk Free Space [HIGH]

The absolute amount of free disk space on the partition where RabbitMQ stores its data (Mnesia
database, message store, WAL).

Collection source: - HTTP Management API: `GET /api/nodes`; fields `disk_free` (bytes),
`disk_free_limit` (bytes)

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Erlang Run Queue Length [HIGH]

The number of Erlang processes waiting in the scheduler run queue to be executed. This is the direct
measure of CPU saturation for the RabbitMQ node.

Collection source: - HTTP Management API: `GET /api/nodes`; field `run_queue` - CLI: `rabbitmqctl
eval 'erlang:statistics(run_queue).'`

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
find_anomalous_metrics filtered by any attribute unique to the RabbitMQ service (usually service.name or host.name)

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
