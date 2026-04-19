# RabbitMQ: Throughput signals

## Scope

Signals in the Throughput domain for RabbitMQ, as defined in the Netdata operator playbook. Each
signal includes a short description, the collection source, and a hint for the MCP query pattern
that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Message Rates (Publish, Deliver, Ack) [HIGH]

The rate of messages published to the broker, delivered to consumers, and acknowledged by consumers,
measured as cumulative counters per second.

Collection source: - HTTP Management API: `GET /api/overview`; field `message_stats` (counters:
`publish`, `deliver`, `deliver_get`, `ack`, `confirm`, `redeliver`, `return_unroutable`, `get`,
`get_no_ack`, `deliver_no_ack`) - Per-queue: `GET /api/queues/{vhost}/{name}`; field `message_stats`
- Per-vhost: `GET /api/...

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Return Unroutable Rate [MEDIUM]

The rate of messages returned to publishers as unroutable; they were published with `mandatory=true`
to an exchange that could not route them to any bound queue.

Collection source: - HTTP Management API: `GET /api/overview`; field
`message_stats.return_unroutable` - Note: Messages published without `mandatory=true` to an exchange
with no matching bindings are silently discarded; they don't appear in any counter.

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

## Netdata contexts that surface Throughput

These are the real Netdata chart contexts the native collector emits for RabbitMQ. Use these names
verbatim in `query_metrics` calls.

- `rabbitmq.messages_rate`: Messages (messages/s). Dimensions: ack, publish, publish_in,
                            publish_out, confirm, deliver.
- `rabbitmq.connection_churn_rate`: Connection churn (operations/s). Dimensions: created, closed.
- `rabbitmq.channel_churn_rate`: Channel churn (operations/s). Dimensions: created, closed.
- `rabbitmq.queue_churn_rate`: Queue churn (operations/s). Dimensions: created, deleted, declared.
- `rabbitmq.node_peer_cluster_link_traffic`: Node Cluster Link Peer Traffic (bytes/s). Dimensions:
                                             received, sent.
- `rabbitmq.vhost_messages_rate`: Vhost messages rate (messages/s). Dimensions: ack, publish,
                                  publish_in, publish_out, confirm, deliver.
- `rabbitmq.queue_messages_rate`: Queue messages rate (messages/s). Dimensions: ack, publish,
                                  publish_in, publish_out, confirm, deliver.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[rabbitmq.messages_rate, rabbitmq.connection_churn_rate, rabbitmq.channel_churn_rate, rabbitmq.queue_churn_rate, rabbitmq.node_peer_cluster_link_traffic, rabbitmq.vhost_messages_rate] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="rabbitmq.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="rabbitmq.messages_rate"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
