---
name: troubleshoot-docker
description: "Use when diagnosing issues with Docker: disk exhaustion, oom cascade, daemon hang/lockup, log explosion, or network isolation failure. Queries Netdata via MCP for Docker health signals, applies the diagnostic tree from the Netdata operator playbook, and recommends remediation."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - troubleshoot
  - mcp
  - docker
---

# Troubleshoot Docker

## When to use this skill

- **Disk exhaustion**: `/var/lib/docker` fills; all container writes fail, daemon halts. #1 cause of
                       Docker outages.
- **OOM cascade**: Container(s) hit memory limit then OOM kill then restart then immediate OOM
                   again. Or: host memory exhaustion then kernel OOM kills unpredictably across
                   containers.
- **Daemon hang/lockup**: Storage driver deadlock, slow disk, lock contention. API calls timeout.
                          Running containers continue serving but cannot be managed.
- **Log explosion**: Default json-file driver has NO rotation. A verbose container fills disk in
                     hours.
- **Network isolation failure**: iptables flush, rule collision, conntrack exhaustion. Containers
                                 lose connectivity.
- **Shim process leak**: Container exits but shim remains, consuming PIDs and memory. Accumulates
                         silently.
- Any time the user reports a Docker service behaving outside its expected envelope (elevated
  errors, latency, saturation, resource exhaustion, or unexpected restarts).
- An on-call engineer is paging on a Netdata alert tied to a Docker instance and wants a structured
  triage path.

## Key facts

- This skill wraps the Netdata operator playbook for Docker. It does not replace the playbook; it
  routes a coding agent through MCP queries against the same signals the playbook relies on.
- Docker is a layered container runtime system. Understanding its internal architecture is essential
  for diagnosing failures, because the layer where a problem occurs determines the operator
  response.
- Dominant failure archetypes the playbook calls out: Disk exhaustion; OOM cascade; Daemon
  hang/lockup; Log explosion; Network isolation failure.
- Netdata observes the signals listed in the rule files via its native collectors, plus any
  OpenTelemetry-shipped metrics that your Docker instrumentation adds. Both paths end at the same
  MCP query surface.
- Netdata's docker collector emits 7 context(s) under `docker.*`. The rule files enumerate which
  contexts surface which domain; the Verification section below names the load-bearing ones
  explicitly.

## Step-by-step

1. Confirm the Docker service is up. Query Netdata via MCP with `list_nodes` and filter by the host
   running the target. A missing node means the symptom is at the network or orchestrator layer, not
   inside the service.
2. Pull the last 15 minutes of signals for the target. Use `query_metrics` against the contexts
   listed in the domain rule files. Run `find_anomalous_metrics` in parallel over the same window;
   anomalies frame which rule file to read first.
3. Check for **Disk exhaustion**. `/var/lib/docker` fills; all container writes fail, daemon halts.
   #1 cause of Docker outages. Inspect the rule file whose signals move first for this mode.
4. Check for **OOM cascade**. Container(s) hit memory limit then OOM kill then restart then
   immediate OOM again. Or: host memory exhaustion then kernel OOM kills unpredictably across
   containers. Inspect the rule file whose signals move first for this mode.
5. Check for **Daemon hang/lockup**. Storage driver deadlock, slow disk, lock contention. API calls
   timeout. Running containers continue serving but cannot be managed. Inspect the rule file whose
   signals move first for this mode.
6. Check for **Log explosion**. Default json-file driver has NO rotation. A verbose container fills
   disk in hours. Inspect the rule file whose signals move first for this mode.
7. Check for **Network isolation failure**. iptables flush, rule collision, conntrack exhaustion.
   Containers lose connectivity. Inspect the rule file whose signals move first for this mode.
8. Correlate with host-level signals (`system.cpu.utilization`, `system.memory.usage`,
   `system.disk.io_time`). Many service-level failures have a host-resource precursor.
9. Apply the remediation hinted at in the matching rule file or the operator playbook. Re-run the
   MCP queries from the Verification section to confirm the signals returned to expected ranges. A
   fix that does not move the signal back is not a fix.

### Handy MCP call templates

```text
# Discover metrics from Docker
list_metrics with q="docker"

# Pull a specific context over the last window
query_metrics with context="docker.containers_health_status", relative_window=-15m

# Rank anomalies for the service or host
find_anomalous_metrics with node=<host> and context_pattern="docker.*"

# Correlate a known problem context with others
find_correlated_metrics around the incident window

# Show current alert state
list_raised_alerts scoped to the node
```

## Common mistakes

- Treating Docker as a generic HTTP or process health check. Docker has specific failure archetypes
  (see Key facts) that generic checks miss.
- Stopping at the first anomalous metric. Several archetypes produce correlated spikes; use
  `find_correlated_metrics` to widen the search before concluding a root cause.
- Quoting percentile latency without the sample count. Low traffic plus a single slow request moves
  p99 by seconds.
- Reading dashboards for a window shorter than the failure's fingerprint. Slow-brew failures (queue
  growth, bloat, memory fragmentation) need 30+ minutes of data to see the trend.
- Skipping the host-level correlation. A process-level fix for a noisy-neighbour problem does not
  hold.
- Assuming alert thresholds are tuned for your workload. Tune against observed Docker traffic before
  escalating an alert configuration issue.

## Verification

Run these MCP queries against the Netdata instance that sees the Docker service. Every context
listed below is a real Netdata chart name; the agent does not need to guess.

```text
1. list_metrics filtered by q="docker" (returns every docker.* context Netdata sees)
2. query_metrics with contexts=[docker.containers_health_status, docker.container_health_status, docker.containers_state, docker.images, docker.images_size, docker.container_state] and relative_window=-30m
3. find_anomalous_metrics filtered by node=<host> and context_pattern="docker.*"
```

Load-bearing contexts for this service:

- `docker.containers_health_status`: Total number of Docker containers in various health states
                                     (containers). Dimensions: healthy, unhealthy,
                                     not_running_unhealthy, starting, no_healthcheck.
- `docker.container_health_status`: Docker container health status (status). Dimensions: healthy,
                                    unhealthy, not_running_unhealthy, starting, no_healthcheck.
- `docker.containers_state`: Total number of Docker containers in various states (containers).
                             Dimensions: running, paused, stopped.
- `docker.images`: Total number of Docker images in various states (images). Dimensions: active,
                   dangling.
- `docker.images_size`: Total size of all Docker images (bytes). Dimensions: size.
- `docker.container_state`: Docker container state (state). Dimensions: running, paused, exited,
                            created, restarting, removing.

A clean result means every context is within its expected band and the `find_anomalous_metrics` list
is empty or contains only already-acknowledged items. If the fix was real, re-running the same
queries 10 minutes after applying it will show a clean result. If it does not, revert and look
deeper.

### When the fix does not hold

If signals drift back into the anomalous range within 30 minutes of a remediation, the cause was
deeper than the applied change. Typical misdiagnoses for Docker:

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
