# Varnish Cache: Saturation & Resources signals

## Scope

Signals in the Saturation & Resources domain for Varnish Cache, as defined in the Netdata operator playbook. Each signal includes a short description, the collection source, and a hint for the MCP query pattern that surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Thread Pool Saturation [HIGH]

The degree to which the worker thread pool is exhausted. Measured by the session queue length and ratio of current threads to maximum.

Collection source: - `MAIN.threads`; current total threads (gauge) - `MAIN.thread_queue_len`; current session queue length (gauge) - `MAIN.threads_limited`; count of times thread creation was limited by `thread_pool_max` (counter) - `MAIN.threads_failed`; count of times OS refused thread creation (counter)

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Storage Utilization [HIGH]

How much of the configured cache storage is in use versus available.

Collection source: Per-storage counters: - `SMA.{name}.g_bytes`; bytes currently in use (gauge) - `SMA.{name}.g_space`; bytes currently available (gauge) - `SMA.{name}.c_fail`; allocation failures (counter) Where `{name}` is the storage name: `s0` for primary storage, `Transient` for transient storage.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### LRU Eviction Rate [MEDIUM]

Rate at which objects are forcefully evicted from cache because storage is full, versus expiring naturally via TTL.

Collection source: - `MAIN.n_lru_nuked`; LRU nuked objects (counter) - `MAIN.n_expired`; expired objects (counter)

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Workspace Overflow [MEDIUM]

Failures caused by HTTP requests/responses exceeding allocated workspace memory.

Collection source: - `MAIN.ws_client_overflow`; client workspace overflow (counter, V6+) - `MAIN.ws_backend_overflow`; backend workspace overflow (counter, V6+) - `MAIN.ws_thread_overflow`; thread workspace overflow (counter, V6+) - `MAIN.ws_session_overflow`; session workspace overflow (counter, V6+) - `MAIN.clien...

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use `find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### File Descriptor Pressure [MEDIUM]

Whether the Varnish child process is approaching its file descriptor limit. Every client connection and backend connection consumes an FD.

Collection source: - `MAIN.sess_fail`; session accept failures (counter, includes FD exhaustion) - `MAIN.sess_fail_emfile`; session failures specifically due to EMFILE (too many open files) (counter, V6+) - Process-level: `/proc/{child_pid}/fd` count vs `/proc/{child_pid}/limits`

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
find_anomalous_metrics filtered by any attribute unique to the Varnish Cache service (usually service.name or host.name)

# Look for correlated signals outside this domain
find_correlated_metrics around the incident window, limit 15
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
