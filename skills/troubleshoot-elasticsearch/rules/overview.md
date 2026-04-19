# Elasticsearch: Overview signals

## Scope

Signals in the Overview domain for Elasticsearch, as defined in the Netdata operator playbook. Each
signal includes a short description, the collection source, and a hint for the MCP query pattern
that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

No structured signal list was extracted from the playbook for the Overview domain. Fall back to the
MCP discovery pattern: run `list_metrics` filtered by the Elasticsearch service and inspect anything
with matching keywords.

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

## Netdata contexts that surface Overview

These are the real Netdata chart contexts the native collector emits for Elasticsearch. Use these
names verbatim in `query_metrics` calls.

- `elasticsearch.node_indices_indexing`: Indexing Operations (operations/s). Dimensions: index.
- `elasticsearch.node_indices_indexing_current`: Indexing Operations Current (operations).
                                                 Dimensions: index.
- `elasticsearch.node_indices_indexing_time`: Time Spent On Indexing Operations (milliseconds).
                                              Dimensions: index.
- `elasticsearch.node_indices_search`: Search Operations (operations/s). Dimensions: queries,
                                       fetches.
- `elasticsearch.node_indices_search_current`: Search Operations Current (operations). Dimensions:
                                               queries, fetches.
- `elasticsearch.node_indices_search_time`: node_indices_search_time (milliseconds). Dimensions:
                                            queries, fetches.
- `elasticsearch.node_indices_refresh`: Refresh Operations (operations/s). Dimensions: refresh.
- `elasticsearch.node_indices_refresh_time`: Time Spent On Refresh Operations (milliseconds).
                                             Dimensions: refresh.
- `elasticsearch.node_indices_flush`: Flush Operations (operations/s). Dimensions: flush.
- `elasticsearch.node_indices_flush_time`: Time Spent On Flush Operations (milliseconds).
                                           Dimensions: flush.
- `elasticsearch.node_indices_fielddata_memory_usage`: Fielddata Cache Memory Usage (bytes).
                                                       Dimensions: used.
- `elasticsearch.node_indices_fielddata_evictions`: Fielddata Evictions (operations/s). Dimensions:
                                                    evictions.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[elasticsearch.node_indices_indexing, elasticsearch.node_indices_indexing_current, elasticsearch.node_indices_indexing_time, elasticsearch.node_indices_search, elasticsearch.node_indices_search_current, elasticsearch.node_indices_search_time] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="elasticsearch.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="elasticsearch.node_indices_indexing"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
