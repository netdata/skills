# MongoDB: Overview signals

## Scope

Signals in the Overview domain for MongoDB, as defined in the Netdata operator playbook. Each signal
includes a short description, the collection source, and a hint for the MCP query pattern that
surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

No structured signal list was extracted from the playbook for the Overview domain. Fall back to the
MCP discovery pattern: run `list_metrics` filtered by the MongoDB service and inspect anything with
matching keywords.

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

These are the real Netdata chart contexts the native collector emits for MongoDB. Use these names
verbatim in `query_metrics` calls.

- `mongodb.operations_rate`: Operations rate (operations/s). Dimensions: reads, writes, commands.
- `mongodb.operations_latency_time`: Operations Latency (milliseconds). Dimensions: reads, writes,
                                     commands.
- `mongodb.operations_by_type_rate`: Operations by type (operations/s). Dimensions: insert, query,
                                     update, delete, getmore, command.
- `mongodb.document_operations_rate`: Document operations (operations/s). Dimensions: inserted,
                                      deleted, returned, updated.
- `mongodb.scanned_indexes_rate`: Scanned indexes (indexes/s). Dimensions: scanned.
- `mongodb.scanned_documents_rate`: Scanned documents (documents/s). Dimensions: scanned.
- `mongodb.active_clients_count`: Connected clients (clients). Dimensions: readers, writers.
- `mongodb.queued_operations_count`: Queued operations because of a lock (operations). Dimensions:
                                     reads, writes.
- `mongodb.cursors_open_count`: Open cursors (cursors). Dimensions: open.
- `mongodb.cursors_open_no_timeout_count`: Open cursors with disabled timeout (cursors). Dimensions:
                                           open_no_timeout.
- `mongodb.cursors_opened_rate`: Opened cursors rate (cursors/s). Dimensions: opened.
- `mongodb.cursors_timed_out_rate`: Timed-out cursors (cursors/s). Dimensions: timed_out.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[mongodb.operations_rate, mongodb.operations_latency_time, mongodb.operations_by_type_rate, mongodb.document_operations_rate, mongodb.scanned_indexes_rate, mongodb.scanned_documents_rate] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="mongodb.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="mongodb.operations_rate"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
