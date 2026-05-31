# Stock alert equivalents

Netdata ships 137 health files under `src/health/health.d/`. Before
translating any rule, check whether a stock alert already covers the
signal. For common infrastructure rules the answer is usually yes, and
the right action is to enable or tune the stock alert, not hand-write
one.

## How to find a stock alert

- Browse the stock library in the Netdata repo:
  `src/health/health.d/` (one file per technology, for example
  `cpu.conf`, `disks.conf`, `mysql.conf`).
- On a running node, list loaded alerts with
  `GET /api/v1/alarms?all` or the MCP `list_running_alerts` tool, and
  match by context.
- Stock alerts are `template:`-based: they auto-attach to every chart
  of their context, so one stock template covers all disks, all
  interfaces, or all database instances with no per-instance config.

## Common Prometheus signal to Netdata stock alert

The metric names below are node_exporter / common-exporter style. Each
row means "do not translate; enable or tune the named stock alert."

| Prometheus signal | Netdata stock alert | Context |
| --- | --- | --- |
| high CPU (`node_cpu_seconds_total`) | `10min_cpu_usage` | `system.cpu` |
| CPU iowait / steal | `10min_cpu_iowait`, `20min_steal_cpu` | `system.cpu` |
| memory pressure (`MemAvailable`) | `ram_in_use`, `ram_available` | `system.ram`, `mem.available` |
| OOM kills | `oom_kill` | `mem.oom_kill` |
| high load | `load_average_1` / `_5` / `_15` | `system.load` |
| low disk space | `disk_space_usage` | `disk.space` |
| inode exhaustion | `disk_inode_usage` | `disk.inodes` |
| disk filling up (`predict_linear`) | `out_of_disk_space_time` | `disk.space` |
| disk I/O saturation | `10min_disk_utilization`, `10min_disk_backlog` | `disk.util`, `disk.backlog` |
| file descriptors | `system_file_descriptors_utilization` | `system.file_nr_utilization` |
| HTTP endpoint down | `httpcheck_web_service_no_connection` | `httpcheck.status` |
| host unreachable (ICMP) | `ping_host_reachable`, `ping_packet_loss` | `ping.host_packet_loss` |
| TLS cert expiring | `x509check_days_until_expiration` | `x509check.time_until_expiration` |
| NIC errors / drops | `inbound_packets_dropped_ratio`, etc. | `net.drops`, `net.errors` |
| link saturation | `1m_received_traffic_overflow` | `net.net` |
| node rebooted | `system_reboot_detection` | `system.uptime` |
| systemd unit failed | `systemd_service_unit_failed_state` | `systemd.service_unit_state` |
| MySQL replication / conns | `mysql_replication`, `mysql_connections` | `mysql.*` |
| Postgres conns / deadlocks / wraparound | `postgres_total_connection_utilization`, etc. | `postgres.*` |
| Redis persistence / replication | `redis_bgsave_broken`, `redis_master_link_down` | `redis.*` |
| k8s deployment unavailable | `k8s_state_deployment_condition_available` | `k8s_state.deployment_conditions` |
| nginx/apache 5xx | `web_log_1m_internal_errors` | `web_log.type_requests` |

Notes:
- There is no `nginx.conf`. Nginx and Apache are covered by
  `web_log.conf` (access-log analysis) plus `httpcheck.conf` /
  `portcheck.conf`. The `web_log` alerts guard on traffic volume
  before alerting on a ratio.
- `disk_space_usage` critical is compound: the percentage threshold
  AND `$avail < 5` GB, so it does not false-alarm on very large disks.
- The disk-fill alerts (`out_of_disk_space_time`) are Netdata's native
  answer to Prometheus `predict_linear` filesystem rules.

## How to enable or tune a stock alert

Many stock alerts ship with `to: silent`, meaning they evaluate but
do not notify until you route them. To enable notifications, set a
role on the `to:` line. To change a threshold, override the alert in a
drop-in file under `/etc/netdata/health.d/`.

Copy the stock entity, change only what differs, and reload:

```text
   template: disk_space_usage
         on: disk.space
chart labels: mount_point=!/dev !/dev/* !/run !/run/* *
        calc: $used * 100 / ($avail + $used)
       units: %
       every: 1m
        warn: $this > (($status >= $WARNING ) ? (70) : (80))
        crit: ($this > (($status == $CRITICAL) ? (85) : (90))) && $avail < 5
          to: sysadmin
```

```bash
sudo ./edit-config health.d/disk_space_usage.conf   # from /etc/netdata
sudo netdatacli reload-health
```

Because the alarm name (`disk_space_usage`) matches the stock one, the
drop-in overrides the stock definition rather than adding a duplicate.
Keep the `on:` context identical so it attaches to the same charts.

## When no stock alert matches

If the signal is application-specific or the context is not in the
table, translate the rule. See
[`translate-rules.md`](./translate-rules.md). First confirm Netdata
collects the metric (see
[`choose-what-to-migrate.md`](./choose-what-to-migrate.md), Step 2).

## References

- Stock health library: `src/health/health.d/` in the Netdata repo.
- Health configuration reference: `src/health/REFERENCE.md`.
