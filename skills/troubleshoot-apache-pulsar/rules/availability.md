# Apache Pulsar: Availability signals

## Scope

Signals in the Availability domain for Apache Pulsar, as defined in the Netdata operator playbook. Each signal includes a short description, the collection source, and a hint for the MCP query pattern that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Broker Process Health [MED]

Whether the broker process is running and its HTTP admin endpoint is responding. This is the most basic liveness check; is the broker alive?

Collection source: Broker HTTP admin endpoint: `GET http://<broker-host>:8080/metrics` (if the endpoint responds, the broker process is alive and serving).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Bookie Process Health [MED]

Whether the bookie process is running and its HTTP metrics endpoint is responding.

Collection source: Bookie HTTP metrics endpoint: `GET http://<bookie-host>:8000/metrics`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Bookie Server Status [MED]

Whether a bookie is writable, read-only, or unregistered from the cluster.

Collection source: Bookie Prometheus metrics endpoint.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Broker Publish Latency [MED]

Time taken for the broker to accept a message from a producer, persist it through the bookie write path, and acknowledge back to the producer. This is the end-to-end write latency as seen by the broker.

Collection source: Broker Prometheus metrics endpoint: `pulsar_broker_publish_latency` (Summary with quantiles).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Message Publish and Dispatch Rate [MED]

The rate of messages being published to and dispatched from the broker. This is the fundamental throughput signal; is data flowing through the system?

Collection source: Broker Prometheus metrics endpoint: - `pulsar_rate_in` (Gauge, msgs/sec published; per topic) - `pulsar_rate_out` (Gauge, msgs/sec dispatched; per topic) - `pulsar_throughput_in` (Gauge, bytes/sec published) - `pulsar_throughput_out` (Gauge, bytes/sec dispatched) - Broker-level aggregates: `pulsa...

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Broker Lookup Failures [MED]

The rate of failed topic lookup operations. Topic lookups are how producers and consumers discover which broker owns their topic; if lookups fail, new connections cannot be established even though the broker process is running.

Collection source: Broker Prometheus metrics endpoint: - `pulsar_broker_lookup` (Counter/Gauge, total lookups) - `pulsar_broker_lookup_failures` (Counter/Gauge, failed lookups) - `pulsar_broker_lookup_answers` (Counter/Gauge, successful lookups)

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
find_anomalous_metrics filtered by any attribute unique to the Apache Pulsar service (usually service.name or host.name)

# Look for correlated signals outside this domain
find_correlated_metrics around the incident window, limit 15
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
