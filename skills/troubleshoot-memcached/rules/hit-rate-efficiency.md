# Memcached: HIT RATE & EFFICIENCY signals

## Scope

Signals in the HIT RATE & EFFICIENCY domain for Memcached, as defined in the Netdata operator
playbook. Each signal includes a short description, the collection source, and a hint for the MCP
query pattern that surfaces it. Use this file during a triage pass to decide which signal to pull
first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Cache Hit Ratio [MED]

The percentage of GET requests served from cache (hits) versus misses. The primary effectiveness
metric.

Collection source: `stats` command then fields `get_hits`, `get_misses`. Formula: `hit_ratio =
get_hits / (get_hits + get_misses)`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Eviction Rate [MED]

The rate at which valid, non-expired items are forcibly removed from memory to make space for new
items. This is the primary memory pressure signal.

Collection source: `stats` command then field `evictions` (cumulative counter).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Eviction Age (evicted_time) [MED]

The age (seconds since last access) of the most recently evicted item, reported per slab class. This
is the critical discriminator between healthy and harmful evictions.

Collection source: `stats items` command then per-slab field `evicted_time` (seconds since last
access of last evicted item).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Evicted Unfetched / Expired Unfetched [MED]

- `evicted_unfetched`: Items evicted from cache that were NEVER read (get/incr/append/etc) after
being set - `expired_unfetched`: Items that expired naturally without ever being read after being
set

Collection source: `stats` command then fields `evicted_unfetched`, `expired_unfetched` (cumulative,
since 1.4.8).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Get Flushed [MED]

GET requests that returned a miss because the item existed in the cache but had been invalidated by
a `flush_all` command.

Collection source: `stats` command then field `get_flushed` (cumulative).

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Store Failures (store_too_large, store_no_memory) [MED]

- `store_too_large`: SET operations rejected because the item exceeded the maximum item size -
`store_no_memory`: SET operations rejected because memory allocation failed (only when `-M` flag is
used, which disables eviction and returns errors instead)

Collection source: `stats` command then fields `store_too_large`, `store_no_memory`.

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
find_anomalous_metrics filtered by any attribute unique to the Memcached service (usually service.name or host.name)

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
