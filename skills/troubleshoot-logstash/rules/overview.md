# Logstash: Overview signals

## Scope

Signals in the Overview domain for Logstash, as defined in the Netdata operator playbook. Each
signal includes a short description, the collection source, and a hint for the MCP query pattern
that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

No structured signal list was extracted from the playbook for the Overview domain. Fall back to the
MCP discovery pattern: run `list_metrics` filtered by the Logstash service and inspect anything with
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

These are the real Netdata chart contexts the native collector emits for Logstash. Use these names
verbatim in `query_metrics` calls.

- `logstash.jvm_threads`: JVM Threads (count). Dimensions: threads.
- `logstash.jvm_mem_heap_used`: JVM Heap Memory Percentage (percentage). Dimensions: in_use.
- `logstash.jvm_mem_heap`: JVM Heap Memory (KiB). Dimensions: committed, used.
- `logstash.jvm_mem_pools_eden`: JVM Pool Eden Memory (KiB). Dimensions: committed, used.
- `logstash.jvm_mem_pools_survivor`: JVM Pool Survivor Memory (KiB). Dimensions: committed, used.
- `logstash.jvm_mem_pools_old`: JVM Pool Old Memory (KiB). Dimensions: committed, used.
- `logstash.jvm_gc_collector_count`: Garbage Collection Count (counts/s). Dimensions: eden, old.
- `logstash.jvm_gc_collector_time`: Time Spent On Garbage Collection (ms). Dimensions: eden, old.
- `logstash.open_file_descriptors`: Open File Descriptors (fd). Dimensions: open.
- `logstash.event`: Events Overview (events/s). Dimensions: in, filtered, out.
- `logstash.event_duration`: Events Duration (seconds). Dimensions: event, queue.
- `logstash.uptime`: Uptime (seconds). Dimensions: uptime.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[logstash.jvm_threads, logstash.jvm_mem_heap_used, logstash.jvm_mem_heap, logstash.jvm_mem_pools_eden, logstash.jvm_mem_pools_survivor, logstash.jvm_mem_pools_old] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="logstash.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="logstash.jvm_threads"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
