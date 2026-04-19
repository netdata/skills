# Kubernetes Cluster State: Etcd Health signals

## Scope

Signals in the Etcd Health domain for Kubernetes Cluster State, as defined in the Netdata operator
playbook. Each signal includes a short description, the collection source, and a hint for the MCP
query pattern that surfaces it. Use this file during a triage pass to decide which signal to pull
first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### etcd Leader Changes [HIGH]

Frequency of etcd leader elections. Each election causes a brief period where writes are blocked.

Collection source: - Metric: `etcd_server_leader_changes_seen_total` (Counter, per-member)

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### etcd Database Size [HIGH]

Current size of the etcd database. etcd has a configurable quota (default 2 GiB, max recommended 8
GiB). Exceeding the quota triggers a NOSPACE alarm that makes the cluster read-only.

Collection source: - Metric: `etcd_mvcc_db_total_size_in_bytes` (Gauge, etcd 3.4+) - Quota metric:
`etcd_server_quota_backend_bytes` (Gauge) - Logical size: `etcd_mvcc_db_total_size_in_use_in_bytes`
(Gauge; actual data; difference from total = reclaimable via defrag)

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### etcd Proposals Failed [MEDIUM]

Count of Raft consensus proposals that failed; writes proposed to the cluster that did not achieve
quorum agreement.

Collection source: - Metric: `etcd_server_proposals_failed_total` (Counter)

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### etcd Peer Round-Trip Time [MEDIUM]

Round-trip time for communication between etcd cluster members.

Collection source: - Metric: `etcd_network_peer_round_trip_time_seconds` (Histogram, labeled by peer
`To`)

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

## Netdata contexts that surface Etcd Health

No Netdata-native contexts were classified into the Etcd Health domain for Kubernetes Cluster State.
Use discovery-style MCP calls below, or consult the full context list in SKILL.md.

## MCP query examples for this domain

```text
# Discover contexts for this service
list_metrics with q="kubernetes-cluster-state"

# Rank anomalies on the host running this service
find_anomalous_metrics with node=<host>
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
