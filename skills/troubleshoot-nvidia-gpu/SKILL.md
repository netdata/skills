---
name: troubleshoot-nvidia-gpu
description: "Use when diagnosing issues with Nvidia Gpu: memory exhaustion (oom), thermal runaway then throttling cascade, silent hardware degradation, interconnect degradation (straggler), or gpu hang / fallen off bus. Queries Netdata via MCP for gpu reachability (driver communication), management path latency / driver health, gpu die temperature, hbm memory temperature, framebuffer memory utilization (vram), applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - nvidia-gpu
---

# Troubleshoot Nvidia Gpu

## When to use this skill

- **Memory exhaustion (OOM)**: Allocation fails immediately. No gradual degradation; it's a cliff.
                               The most common GPU workload failure.
- **Thermal runaway then throttling cascade**: Temperature rises then clocks throttle then
                                               performance collapses then system finds equilibrium
                                               at terrible performance. Workload continues but 2-10x
                                               slower.
- **Silent hardware degradation**: ECC errors accumulate, memory corrupts intermittently, training
                                   produces wrong results before anyone notices. The GPU "works" but
                                   produces garbage.
- **Interconnect degradation (straggler)**: One slow NVLink or degraded PCIe link in a distributed
                                            training job creates a straggler that bottleneck-gates
                                            the entire collective operation.
- **GPU hang / fallen off bus**: GPU becomes unresponsive, nvidia-smi hangs, requires driver reload
                                 or reboot. XID 79 = catastrophic PCIe link failure.
- **Driver/process hang**: Stuck CUDA contexts hold GPU memory indefinitely. Zombie processes
                           prevent resource reclamation. May require `nvidia-smi -r` or reboot.
- Any time the user reports a Nvidia Gpu service behaving outside its expected envelope (elevated
  errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a Nvidia Gpu instance and wants a
  structured triage path.

## Key facts

- This skill wraps the Netdata operator playbook for Nvidia Gpu. It does not replace the playbook;
  it routes a coding agent through MCP queries against the same signals the playbook relies on.
- The playbook decomposes Nvidia Gpu health into 8 signal domains: Availability, Thermal & Power,
  Memory, Compute & Utilization, Interconnect, Errors (Xid). Each domain maps to one rule file in
  this skill.
- Dominant failure archetypes the playbook calls out: Memory exhaustion (OOM); Thermal runaway then
  throttling cascade; Silent hardware degradation; Interconnect degradation (straggler); GPU hang /
  fallen off bus.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your Nvidia Gpu instrumentation adds. Both paths end at the
  same MCP query surface.
- Netdata's nvidia_smi collector emits 18 context(s) under `nvidia_smi.*`. The rule files enumerate
  which contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the Nvidia Gpu service is up. Query Netdata via MCP with `list_nodes` and filter by the
   host running the target. A missing node means the symptom is at the network or orchestrator
   layer, not inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **Memory exhaustion (OOM)**. Allocation fails immediately. No gradual degradation; it's
   a cliff. The most common GPU workload failure. Inspect the rule file whose signals move first for
   this mode.
4. Check for **Thermal runaway then throttling cascade**. Temperature rises then clocks throttle
   then performance collapses then system finds equilibrium at terrible performance. Workload
   continues but 2-10x slower. Inspect the rule file whose signals move first for this mode.
5. Check for **Silent hardware degradation**. ECC errors accumulate, memory corrupts intermittently,
   training produces wrong results before anyone notices. The GPU "works" but produces garbage.
   Inspect the rule file whose signals move first for this mode.
6. Check for **Interconnect degradation (straggler)**. One slow NVLink or degraded PCIe link in a
   distributed training job creates a straggler that bottleneck-gates the entire collective
   operation. Inspect the rule file whose signals move first for this mode.
7. Check for **GPU hang / fallen off bus**. GPU becomes unresponsive, nvidia-smi hangs, requires
   driver reload or reboot. XID 79 = catastrophic PCIe link failure. Inspect the rule file whose
   signals move first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from Nvidia Gpu
list_metrics with q="nvidia_smi"

# Pull a specific context over the last window
query_metrics with context="nvidia_smi.gpu_mig_mode_current_status", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="nvidia_smi.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating Nvidia Gpu as a generic HTTP or process health check. Nvidia Gpu has specific failure
  archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed Nvidia Gpu traffic
  before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the Nvidia Gpu service. Every context
listed below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="nvidia_smi" (returns every nvidia_smi.* context Netdata sees)
2. query_metrics with contexts=[nvidia_smi.gpu_mig_mode_current_status, nvidia_smi.gpu_pcie_bandwidth_usage, nvidia_smi.gpu_memory_utilization, nvidia_smi.gpu_frame_buffer_memory_usage, nvidia_smi.gpu_bar1_memory_usage, nvidia_smi.gpu_mig_frame_buffer_memory_usage] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="nvidia_smi.*"
```

Load-bearing contexts for this service:

- `nvidia_smi.gpu_mig_mode_current_status`: MIG current mode (status). Dimensions: enabled,
                                            disabled.
- `nvidia_smi.gpu_pcie_bandwidth_usage`: PCI Express Bandwidth Usage (B/s). Dimensions: rx, tx.
- `nvidia_smi.gpu_memory_utilization`: Memory utilization (%). Dimensions: memory.
- `nvidia_smi.gpu_frame_buffer_memory_usage`: Frame buffer memory usage (B). Dimensions: free, used,
                                              reserved.
- `nvidia_smi.gpu_bar1_memory_usage`: BAR1 memory usage (B). Dimensions: free, used.
- `nvidia_smi.gpu_mig_frame_buffer_memory_usage`: Frame buffer memory usage (B). Dimensions: free,
                                                  used, reserved.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for Nvidia Gpu:

- Host-resource pressure masquerading as application bug.
- Dependent service (DB, cache, upstream) causing a secondary symptom in the instrumented service.
- Configuration change that was never reloaded (some subsystems only pick up config on full
  restart).

Escalate by widening the query window: 2-6 hours instead of 15 minutes. Slow-moving causes are
invisible at triage window sizes.

## References

- [`rules/availability.md`](./rules/availability.md)
- [`rules/thermal-power.md`](./rules/thermal-power.md)
- [`rules/memory.md`](./rules/memory.md)
- [`rules/compute-utilization.md`](./rules/compute-utilization.md)
- [`rules/interconnect.md`](./rules/interconnect.md)
- [`rules/errors-xid.md`](./rules/errors-xid.md)
- [`rules/distributed-training-multi-gpu.md`](./rules/distributed-training-multi-gpu.md)
- [`rules/security-integrity.md`](./rules/security-integrity.md)
- Netdata operator playbook: the authoritative source material this skill summarizes.
- `skills/netdata-mcp-integration/` for the transport setup.
- `skills/netdata-otel-setup/` if additional application signals are needed beyond what Netdata
  collects natively.
