---
name: troubleshoot-smartctl-disk-monitoring
description: "Use when diagnosing issues with smartctl (S.M.A.R.T. Disk Health): gradual media degradation, sudden mechanical failure, ssd wear-out cliff, interface/transport failure, or thermal damage. Queries Netdata via MCP for smartctl (S.M.A.R.T. Disk Health) health signals, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - smartctl-disk-monitoring
---

# Troubleshoot smartctl (S.M.A.R.T. Disk Health)

## When to use this skill

- **Gradual media degradation**: Bad sectors accumulate over weeks/months.
- **Sudden mechanical failure**: (HDD); Head crash, spindle seizure, or actuator
- **SSD wear-out cliff**: SSDs degrade gradually but fail suddenly. Once the spare
- **Interface/transport failure**: The drive itself is healthy but the physical
- **Thermal damage**: Sustained high temperature degrades components. HDDs: bearing
- **Controller/electronics failure**: Firmware bug, power surge damage, or capacitor
- Any time the user reports a smartctl (S.M.A.R.T. Disk Health) service behaving outside its
  expected envelope (elevated errors, latency, saturation, resource exhaustion, or unexpected
  restarts).
- An on-call engineer is paging on a Netdata alert tied to a smartctl (S.M.A.R.T. Disk Health)
  instance and wants a structured triage path.

## Key facts

- This skill wraps the Netdata operator playbook for smartctl (S.M.A.R.T. Disk Health). It does not
  replace the playbook; it routes a coding agent through MCP queries against the same signals the
  playbook relies on.
- S.M.A.R.T. (Self-Monitoring, Analysis, and Reporting Technology) is firmware-level instrumentation
  embedded in every modern HDD, SSD, and NVMe drive. It is not a monitoring agent; it is the drive
  reporting on its own internal state. The `smartctl` tool (from smartmontools) reads what the drive
  firmware already knows.
- Dominant failure archetypes the playbook calls out: Gradual media degradation; Sudden mechanical
  failure; SSD wear-out cliff; Interface/transport failure; Thermal damage.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your smartctl (S.M.A.R.T. Disk Health) instrumentation adds.
  Both paths end at the same MCP query surface.
- Netdata's smartctl collector emits 10 context(s) under `smartctl.*`. The rule files enumerate
  which contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the smartctl (S.M.A.R.T. Disk Health) service is up. Query Netdata via MCP with
   `list_nodes` and filter by the host running the target. A missing node means the symptom is at
   the network or orchestrator layer, not inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **Gradual media degradation**. Bad sectors accumulate over weeks/months. Inspect the
   rule file whose signals move first for this mode.
4. Check for **Sudden mechanical failure**. (HDD); Head crash, spindle seizure, or actuator Inspect
   the rule file whose signals move first for this mode.
5. Check for **SSD wear-out cliff**. SSDs degrade gradually but fail suddenly. Once the spare
   Inspect the rule file whose signals move first for this mode.
6. Check for **Interface/transport failure**. The drive itself is healthy but the physical Inspect
   the rule file whose signals move first for this mode.
7. Check for **Thermal damage**. Sustained high temperature degrades components. HDDs: bearing
   Inspect the rule file whose signals move first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from smartctl (S.M.A.R.T. Disk Health)
list_metrics with q="smartctl"

# Pull a specific context over the last window
query_metrics with context="smartctl.device_smart_status", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="smartctl.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating smartctl (S.M.A.R.T. Disk Health) as a generic HTTP or process health check. smartctl
  (S.M.A.R.T. Disk Health) has specific failure archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed smartctl (S.M.A.R.T.
  Disk Health) traffic before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the smartctl (S.M.A.R.T. Disk Health)
service. Every context listed below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="smartctl" (returns every smartctl.* context Netdata sees)
2. query_metrics with contexts=[smartctl.device_smart_status, smartctl.device_ata_smart_error_log_count, smartctl.device_read_errors_rate, smartctl.device_write_errors_rate, smartctl.device_verify_errors_rate, smartctl.device_power_on_time] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="smartctl.*"
```

Load-bearing contexts for this service:

- `smartctl.device_smart_status`: Device smart status (status). Dimensions: passed, failed.
- `smartctl.device_ata_smart_error_log_count`: Device ATA smart error log count (logs). Dimensions:
                                               error_log.
- `smartctl.device_read_errors_rate`: Device read errors (errors/s). Dimensions: corrected,
                                      uncorrected.
- `smartctl.device_write_errors_rate`: Device write errors (errors/s). Dimensions: corrected,
                                       uncorrected.
- `smartctl.device_verify_errors_rate`: Device verify errors (errors/s). Dimensions: corrected,
                                        uncorrected.
- `smartctl.device_power_on_time`: Device power on time (seconds). Dimensions: power_on_time.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for smartctl (S.M.A.R.T. Disk Health):

- Host-resource pressure masquerading as application bug.
- Dependent service (DB, cache, upstream) causing a secondary symptom in the instrumented service.
- Configuration change that was never reloaded (some subsystems only pick up config on full
  restart).

Escalate by widening the query window: 2-6 hours instead of 15 minutes. Slow-moving causes are
invisible at triage window sizes.

## References

- [`rules/overview.md`](./rules/overview.md)
- Netdata operator playbook: the authoritative source material this skill summarizes.
- `skills/netdata-mcp-integration/` for the transport setup.
- `skills/netdata-otel-setup/` if additional application signals are needed beyond what Netdata
  collects natively.
