---
name: troubleshoot-nvidia-dcgm
description: "Use when diagnosing issues with NVIDIA DCGM: hbm degradation, thermal runaway/throttling, nvlink errors, gpu hang (xid 13/31/43/79), or silent performance degradation. Queries Netdata via MCP for NVIDIA DCGM health signals, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - nvidia-dcgm
---

# Troubleshoot NVIDIA DCGM

## When to use this skill

- **HBM Degradation**: Progressive ECC errors then row remapping then spare row exhaustion then
                       uncorrectable errors then GPU falls off bus. This is the #1 hardware failure
                       mode. It's slow-moving (weeks to months) and completely predictable if you
                       monitor the right signals.
- **Thermal Runaway/Throttling**: Inlet temperature rises then GPU thermal throttles then clocks
                                  drop then training slows then other GPUs wait at synchronization
                                  barriers then all GPUs run sub-optimally because one is throttled.
- **NVLink Errors**: CRC errors on NVLink lanes then retransmissions then bandwidth reduction then
                     collective operations slow down then multi-GPU training stalls or hangs. Often
                     caused by cable issues, connector problems, or NVSwitch failures.
- **GPU Hang (XID 13/31/43/79)**: GPU firmware or hardware enters an unrecoverable state. Manifests
                                  as processes stuck, CUDA calls not returning, eventually XID error
                                  in dmesg. The GPU may need a reset or the node needs a reboot. XID
                                  79 ("GPU has fallen off the bus") means the PCIe link is lost
                                  entirely.
- **Silent Performance Degradation**: PCIe link running at reduced width (x8 instead of x16) or
                                      reduced speed (Gen3 instead of Gen5). GPU appears healthy,
                                      workloads run, but throughput is halved or worse. Operators
                                      often miss this for weeks.
- **Power Capping**: Chassis-level power management reduces individual GPU power limits. Clocks
                     drop. Training throughput drops proportionally. No errors, no alerts; just
                     slower.
- Any time the user reports a NVIDIA DCGM service behaving outside its expected envelope (elevated
  errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a NVIDIA DCGM instance and wants a
  structured triage path.

## Key facts

- This skill wraps the Netdata operator playbook for NVIDIA DCGM. It does not replace the playbook;
  it routes a coding agent through MCP queries against the same signals the playbook relies on.
- Dominant failure archetypes the playbook calls out: HBM Degradation; Thermal Runaway/Throttling;
  NVLink Errors; GPU Hang (XID 13/31/43/79); Silent Performance Degradation.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your NVIDIA DCGM instrumentation adds. Both paths end at the
  same MCP query surface.
- Netdata's dcgm collector emits 148 context(s) under `dcgm.*`. The rule files enumerate which
  contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the NVIDIA DCGM service is up. Query Netdata via MCP with `list_nodes` and filter by the
   host running the target. A missing node means the symptom is at the network or orchestrator
   layer, not inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **HBM Degradation**. Progressive ECC errors then row remapping then spare row
   exhaustion then uncorrectable errors then GPU falls off bus. This is the #1 hardware failure
   mode. It's slow-moving (weeks to months) and completely predictable if you monitor the right
   signals. Inspect the rule file whose signals move first for this mode.
4. Check for **Thermal Runaway/Throttling**. Inlet temperature rises then GPU thermal throttles then
   clocks drop then training slows then other GPUs wait at synchronization barriers then all GPUs
   run sub-optimally because one is throttled. Inspect the rule file whose signals move first for
   this mode.
5. Check for **NVLink Errors**. CRC errors on NVLink lanes then retransmissions then bandwidth
   reduction then collective operations slow down then multi-GPU training stalls or hangs. Often
   caused by cable issues, connector problems, or NVSwitch failures. Inspect the rule file whose
   signals move first for this mode.
6. Check for **GPU Hang (XID 13/31/43/79)**. GPU firmware or hardware enters an unrecoverable state.
   Manifests as processes stuck, CUDA calls not returning, eventually XID error in dmesg. The GPU
   may need a reset or the node needs a reboot. XID 79 ("GPU has fallen off the bus") means the PCIe
   link is lost entirely. Inspect the rule file whose signals move first for this mode.
7. Check for **Silent Performance Degradation**. PCIe link running at reduced width (x8 instead of
   x16) or reduced speed (Gen3 instead of Gen5). GPU appears healthy, workloads run, but throughput
   is halved or worse. Operators often miss this for weeks. Inspect the rule file whose signals move
   first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from NVIDIA DCGM
list_metrics with q="dcgm"

# Pull a specific context over the last window
query_metrics with context="dcgm.gpu.capability.support", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="dcgm.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating NVIDIA DCGM as a generic HTTP or process health check. NVIDIA DCGM has specific failure
  archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed NVIDIA DCGM traffic
  before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the NVIDIA DCGM service. Every context
listed below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="dcgm" (returns every dcgm.* context Netdata sees)
2. query_metrics with contexts=[dcgm.gpu.capability.support, dcgm.gpu.compute.activity, dcgm.gpu.diagnostics.status, dcgm.gpu.health.status, dcgm.gpu.interconnect.connectx.error_status, dcgm.gpu.interconnect.connectx.errors] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="dcgm.*"
```

Load-bearing contexts for this service:

- `dcgm.gpu.capability.support`: GPU Capability Support metrics. (state). Dimensions: cc_mode,
                                 cuda_compute_capability, gpm_support, mig_attributes, mig_ci_info,
                                 mig_gi_info.
- `dcgm.gpu.compute.activity`: GPU Compute Pipeline Activity metrics. (%). Dimensions: dram, fp16,
                               fp32, fp64, graphics_engine_active, integer.
- `dcgm.gpu.diagnostics.status`: GPU Diagnostics Status metrics. (state). Dimensions: diag_status.
- `dcgm.gpu.health.status`: GPU Health Status metrics. (state). Dimensions: imex_daemon_status,
                            imex_domain_status.
- `dcgm.gpu.interconnect.connectx.error_status`: GPU ConnectX Error Status metrics. (state).
                                                 Dimensions: connectx_correctable_err_mask,
                                                 connectx_correctable_err_status,
                                                 connectx_uncorrectable_err_mask,
                                                 connectx_uncorrectable_err_severity,
                                                 connectx_uncorrectable_err_status.
- `dcgm.gpu.interconnect.connectx.errors`: GPU ConnectX Errors metrics. (errors/s). Dimensions:
                                           connectx_correctable_err_mask,
                                           connectx_correctable_err_status,
                                           connectx_uncorrectable_err_mask,
                                           connectx_uncorrectable_err_severity,
                                           connectx_uncorrectable_err_status.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for NVIDIA DCGM:

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
