# NVMe: Health & Critical Warnings signals

## Scope

Signals in the Health & Critical Warnings domain for NVMe, as defined in the Netdata operator
playbook. Each signal includes a short description, the collection source, and a hint for the MCP
query pattern that surfaces it. Use this file during a triage pass to decide which signal to pull
first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### SMART Critical Warning; Read-Only Mode (Bit 3) [HIGH]

The drive has placed its media in read-only mode. All write commands will be rejected.

Collection source: NVMe SMART log, `critical_warning` bitmask, bit 3. Netdata dimension: `read_only`
in chart `nvme.device_critical_warnings_state`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### SMART Critical Warning; NVM Subsystem Reliability Degraded (Bit 2) [HIGH]

The controller has detected significant media-related errors or internal failures that have degraded
the subsystem's reliability.

Collection source: NVMe SMART log, `critical_warning` bitmask, bit 2. Netdata dimension:
`nvm_subsystem_reliability` in chart `nvme.device_critical_warnings_state`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### SMART Critical Warning; Available Spare Below Threshold (Bit 0) [HIGH]

Available spare capacity has fallen below the vendor-defined threshold.

Collection source: NVMe SMART log, `critical_warning` bitmask, bit 0. Netdata dimension:
`available_spare` in chart `nvme.device_critical_warnings_state`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### SMART Critical Warning; Temperature Threshold Exceeded (Bit 1) [HIGH]

Temperature has exceeded either the Warning Composite Temperature Threshold (WCTEMP) or Critical
Composite Temperature Threshold (CCTEMP).

Collection source: NVMe SMART log, `critical_warning` bitmask, bit 1. Netdata dimension:
`temp_threshold` in chart `nvme.device_critical_warnings_state`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### SMART Critical Warning; Volatile Memory Backup Failed (Bit 4) [HIGH]

The power-loss protection (PLP) capacitor has failed on an enterprise drive with PLP.

Collection source: NVMe SMART log, `critical_warning` bitmask, bit 4. Netdata dimension:
`volatile_mem_backup_failed` in chart `nvme.device_critical_warnings_state`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### SMART Critical Warning; Persistent Memory Region Read-Only (Bit 5) [MEDIUM]

The Persistent Memory Region has become read-only. Only relevant for NVMe 1.4+ devices with PMR.

Collection source: NVMe SMART log, `critical_warning` bitmask, bit 5. Netdata dimension:
`persistent_memory_read_only` in chart `nvme.device_critical_warnings_state`.

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
find_anomalous_metrics filtered by any attribute unique to the NVMe service (usually service.name or host.name)

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
