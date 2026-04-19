# Apache Pulsar: Latency signals

## Scope

Signals in the Latency domain for Apache Pulsar, as defined in the Netdata operator playbook. Each
signal includes a short description, the collection source, and a hint for the MCP query pattern
that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Bookie Journal Sync Latency [MED]

The time taken to fsync the write-ahead journal to disk. This is the physical limit of Pulsar's
write throughput and the single most critical latency metric in the entire Pulsar stack.

Collection source: Bookie Prometheus metrics endpoint: `bookie_journal_JOURNAL_SYNC` (Summary with
quantiles and `journalIndex` label).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Metadata Store Request Latency [MED]

Round-trip time for metadata operations from broker to the metadata store (ZooKeeper in most
deployments). Covers reads, writes, and watch notifications for cluster coordination.

Collection source: Broker Prometheus metrics endpoint. The exact metric name depends on the Pulsar
version and metadata store abstraction layer. Look for ZK-related latency metrics in the broker's
`/metrics` output.

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

## Netdata contexts that surface Latency

These are the real Netdata chart contexts the native collector emits for Apache Pulsar. Use these
names verbatim in `query_metrics` calls.

- `pulsar.storage_write_latency`: Storage Write Latency (entries/s). Dimensions: <=0.5ms, <=1ms,
                                  <=5ms, =10ms, <=20ms, <=50ms.
- `pulsar.namespace_storage_write_latency`: Storage Write Latency (entries/s). Dimensions: <=0.5ms,
                                            <=1ms, <=5ms, =10ms, <=20ms, <=50ms.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[pulsar.storage_write_latency, pulsar.namespace_storage_write_latency] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="pulsar.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="pulsar.storage_write_latency"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
