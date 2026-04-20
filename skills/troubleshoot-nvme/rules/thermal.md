# NVMe: Thermal signals

## Scope

Signals in the Thermal domain for NVMe, as defined in the Netdata operator playbook. Each signal
includes a short description, the collection source, and a hint for the MCP query pattern that
surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

### Composite Temperature [HIGH]

Current operating temperature as reported by the controller, typically the highest of controller and
NAND die temperatures.

Collection source: NVMe SMART log, `temperature` field (Kelvin in JSON; subtract 273.15 for
Celsius). Also via hwmon: `/sys/class/nvme/nvmeX/hwmon*/temp1_input` (millidegrees Celsius). Netdata
context: `nvme.device_composite_temperature`, dimension: `temperature`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Warning Composite Temperature Time [MEDIUM]

Cumulative time (minutes) the composite temperature has been above WCTEMP.

Collection source: NVMe SMART log, `warning_temp_time` (minutes, converted to seconds by Netdata).
Netdata context: `nvme.device_warning_composite_temperature_time`, dimension: `wctemp`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Critical Composite Temperature Time [MEDIUM]

Cumulative time (minutes) the composite temperature has been above CCTEMP.

Collection source: NVMe SMART log, `critical_comp_time` (minutes, converted to seconds by Netdata).
Netdata context: `nvme.device_critical_composite_temperature_time`, dimension: `cctemp`.

MCP query: pull this signal with `query_metrics` and check the last 15 to 30 minutes against
expected bands. Cross-reference with `find_anomalous_metrics` scoped to the same context. Use
`find_correlated_metrics` if the signal has moved but the obvious cause is not visible.

### Thermal Management Transitions and Time [MEDIUM]

Count of transitions into thermal management states (TMT1, TMT2) and time spent there.

Collection source: NVMe SMART log: `thm_temp1_trans_count`, `thm_temp2_trans_count`,
`thm_temp1_total_time`, `thm_temp2_total_time`. Netdata contexts:
`nvme.device_thermal_mgmt_temp{1,2}_transitions_rate` and `nvme.device_thermal_mgmt_temp{1,2}_time`.

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

## Netdata contexts that surface Thermal

These are the real Netdata chart contexts the native collector emits for NVMe. Use these names
verbatim in `query_metrics` calls.

- `nvme.device_thermal_mgmt_temp1_transitions_rate`: Thermal management temp1 transitions
                                                     (transitions/s). Dimensions: temp1.
- `nvme.device_thermal_mgmt_temp2_transitions_rate`: Thermal management temp2 transitions
                                                     (transitions/s). Dimensions: temp2.
- `nvme.device_thermal_mgmt_temp1_time`: Thermal management temp1 time (seconds). Dimensions: temp1.
- `nvme.device_thermal_mgmt_temp2_time`: Thermal management temp2 time (seconds). Dimensions: temp2.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[nvme.device_thermal_mgmt_temp1_transitions_rate, nvme.device_thermal_mgmt_temp2_transitions_rate, nvme.device_thermal_mgmt_temp1_time, nvme.device_thermal_mgmt_temp2_time] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="nvme.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="nvme.device_thermal_mgmt_temp1_transitions_rate"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
