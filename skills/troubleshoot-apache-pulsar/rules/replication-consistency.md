# Apache Pulsar: Replication & Consistency signals

## Scope

Signals in the Replication & Consistency domain for Apache Pulsar, as defined in the Netdata
operator playbook. Each signal includes a short description, the collection source, and a hint for
the MCP query pattern that surfaces it. Use this file during a triage pass to decide which signal to
pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Under-Replicated Ledger Count [MED]

The number of BookKeeper ledgers that do not have enough valid copies across the bookie cluster.
Under-replicated ledgers are at risk of data loss if additional bookie failures occur.

Collection source: BookKeeper auditor Prometheus metrics: `auditor_NUM_UNDER_REPLICATED_LEDGERS`
(Summary, on the auditor node). BookKeeper shell command for manual inspection.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Geo-Replication Backlog [MED]

The number of messages pending replication to a remote cluster. Only applicable when geo-replication
is configured.

Collection source: Broker Prometheus metrics endpoint: - `pulsar_replication_backlog` (Gauge,
labels: `{cluster, namespace, topic, remoteCluster}`) - `pulsar_replication_delay_in_seconds`
(Gauge, lag time) - `pulsar_replication_connected_count` / `pulsar_replication_disconnected_count`
(Gauge)

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

## Netdata contexts that surface Replication & Consistency

These are the real Netdata chart contexts the native collector emits for Apache Pulsar. Use these
names verbatim in `query_metrics` calls.

- `pulsar.replication_rate`: Replication Rate (messages/s). Dimensions: in, out.
- `pulsar.replication_throughput_rate`: Replication Throughput Rate (KiB/s). Dimensions: in, out.
- `pulsar.replication_backlog`: Replication Backlog (messages). Dimensions: backlog.
- `pulsar.namespace_replication_rate`: Replication Rate (messages/s). Dimensions: in, out.
- `pulsar.namespace_replication_throughput_rate`: Replication Throughput Rate (KiB/s). Dimensions:
                                                  in, out.
- `pulsar.namespace_replication_backlog`: Replication Backlog (messages). Dimensions: backlog.
- `pulsar.topic_replication_rate_in`: Topic Replication Rate From Remote Cluster (messages/s).
- `pulsar.topic_replication_rate_out`: Topic Replication Rate To Remote Cluster (messages/s).
- `pulsar.topic_replication_throughput_rate_in`: Topic Replication Throughput Rate From Remote
                                                 Cluster (messages/s).
- `pulsar.topic_replication_throughput_rate_out`: Topic Replication Throughput Rate To Remote
                                                  Cluster (messages/s).
- `pulsar.topic_replication_backlog`: Topic Replication Backlog (messages).

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[pulsar.replication_rate, pulsar.replication_throughput_rate, pulsar.replication_backlog, pulsar.namespace_replication_rate, pulsar.namespace_replication_throughput_rate, pulsar.namespace_replication_backlog] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="pulsar.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="pulsar.replication_rate"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
