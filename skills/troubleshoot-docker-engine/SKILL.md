---
name: troubleshoot-docker-engine
description: "Use when diagnosing issues with Docker Engine: Docker Engine operational issues. Queries Netdata via MCP for Docker Engine health signals, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - docker-engine
---

# Troubleshoot Docker Engine

## When to use this skill

- Any time the user reports a Docker Engine service behaving outside its expected envelope (elevated
  errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a Docker Engine instance and wants a
  structured triage path.

## Key facts

- This skill wraps the Netdata operator playbook for Docker Engine. It does not replace the
  playbook; it routes a coding agent through MCP queries against the same signals the playbook
  relies on.
- Docker Engine is not one daemon; it is a layered control plane with four distinct process tiers,
  each with independent failure modes:
- 1. **`dockerd`**; The API server and orchestration layer. Listens on `/var/run/docker.sock`
  (rootful) or `/run/user/<UID>/docker.sock` (rootless). Manages images, containers, networks,
  volumes, builds, and logging configuration. Maintains in-memory state backed by on-disk metadata
  (BoltDB stores at multiple subdirectory paths under `/var/lib/docker/`). Written in Go with heavy
  goroutine concurr...
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your Docker Engine instrumentation adds. Both paths end at the
  same MCP query surface.
- Netdata's docker_engine collector emits 8 context(s) under `docker_engine.*`. The rule files
  enumerate which contexts surface which domain; the Verification section below names the
  load-bearing ones explicitly.

## Step-by-step

1. Confirm the Docker Engine service is up. Query Netdata via MCP with `list_nodes` and filter by
   the host running the target. A missing node means the symptom is at the network or orchestrator
   layer, not inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
4. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from Docker Engine
list_metrics with q="docker_engine"

# Pull a specific context over the last window
query_metrics with context="docker_engine.builder_builds_failed_total", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="docker_engine.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating Docker Engine as a generic HTTP or process health check. Docker Engine has specific
  failure archetypes (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed Docker Engine traffic
  before escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the Docker Engine service. Every
context listed below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="docker_engine" (returns every docker_engine.* context Netdata sees)
2. query_metrics with contexts=[docker_engine.builder_builds_failed_total, docker_engine.engine_daemon_health_checks_failed_total, docker_engine.swarm_manager_nodes_per_state, docker_engine.swarm_manager_tasks_per_state, docker_engine.engine_daemon_container_actions, docker_engine.engine_daemon_container_states_containers] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="docker_engine.*"
```

Load-bearing contexts for this service:

- `docker_engine.builder_builds_failed_total`: Builder Builds Fails By Reason (fails/s). Dimensions:
                                               build_canceled, build_target_not_reachable_error,
                                               command_not_supported_error, dockerfile_empty_error,
                                               dockerfile_syntax_error,
                                               error_processing_commands_error.
- `docker_engine.engine_daemon_health_checks_failed_total`: Health Checks (events/s). Dimensions:
                                                            fails.
- `docker_engine.swarm_manager_nodes_per_state`: Swarm Manager Nodes Per State (nodes). Dimensions:
                                                 ready, down, unknown, disconnected.
- `docker_engine.swarm_manager_tasks_per_state`: Swarm Manager Tasks Per State (tasks). Dimensions:
                                                 running, failed, ready, rejected, starting,
                                                 shutdown.
- `docker_engine.engine_daemon_container_actions`: Container Actions (actions/s). Dimensions:
                                                   changes, commit, create, delete, start.
- `docker_engine.engine_daemon_container_states_containers`: Containers In Various States
                                                             (containers). Dimensions: running,
                                                             paused, stopped.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for Docker Engine:

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
