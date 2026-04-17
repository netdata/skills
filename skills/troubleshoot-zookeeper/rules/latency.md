# Apache ZooKeeper: Latency signals

## Scope

Signals in the Latency domain for Apache ZooKeeper, as defined in the Netdata operator playbook.
Each signal includes a short description, the collection source, and a hint for the MCP query
pattern that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Request Latency (Aggregated) [HIGH]

Average, minimum, and maximum latency across all request types (reads + writes) processed by this
node. These are server-cumulative statistics (not rolling averages); they accumulate since last
reset via `srst` command or restart.

Collection source: `mntr` fields `zk_avg_latency`, `zk_min_latency`, `zk_max_latency`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Write Latency (Update Latency) [HIGH]

Latency of write operations specifically (create, setData, delete, setACL), separated from reads.
Available with percentile breakdowns: avg, min, max, p50, p95, p99, p999. This is the most accurate
write-path health signal.

Collection source: `mntr` fields `zk_avg_updatelatency`, `zk_p99_updatelatency`, etc. Available in
ZK 3.6+.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Read Latency [MEDIUM]

Latency of read operations (getData, getChildren, exists). Reads are served locally from memory; no
quorum interaction. Available with percentiles.

Collection source: `mntr` fields `zk_avg_readlatency`, `zk_p99_readlatency`, etc. Available in ZK
3.6+.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Fsync Time [HIGH]

Time taken to fsync the transaction log to disk. This is the single most critical I/O operation in
ZooKeeper; every write blocks until fsync completes. Available with percentiles: avg, min, max, p50,
p95, p99, p999 (ZK 3.6+). In ZK 3.4.x, `zk_fsync_threshold_exceed_count` tracks how often fsync
exceeded the configured threshold.

Collection source: `mntr` fields `zk_avg_fsynctime`, `zk_p99_fsynctime`, etc. (ZK 3.6+) `mntr` field
`zk_fsync_threshold_exceed_count` (ZK 3.4.x)

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Quorum Ack Latency [HIGH]

Time between the leader sending a PROPOSE message and receiving quorum acknowledgments from
followers. This captures network + follower processing time. Available with percentiles. Leader-only
metric.

Collection source: `mntr` fields `zk_avg_quorum_ack_latency`, `zk_p99_quorum_ack_latency`, etc.

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
find_anomalous_metrics filtered by any attribute unique to the Apache ZooKeeper service (usually service.name or host.name)

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
