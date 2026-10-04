# Enable the OTLP/gRPC receiver

## Scope

Bring the `otel-plugin` online and accept OTLP/gRPC traffic on a specific
network endpoint. Covers the stock defaults, minimal user override, bind
address choices, and restart flow.

## Default behavior

Out of the box, the plugin listens on `127.0.0.1:4317` (gRPC only). Metrics,
logs, and traces are all accepted on the same port. Traces need an Agent
built from `master` after 2026-08-17 (nightly) or the first stable release
after v2.11.1; stable v2.11.x does not register a trace service.

Stock settings, reproduced from the shipped `otel.yaml` on a nightly
Agent (comments removed; Linux package paths):

```yaml
endpoint:
  path: "127.0.0.1:4317"
  tls_cert_path: null
  tls_key_path: null
  tls_ca_cert_path: null

metrics:
  chart_configs_dir: /etc/netdata/otel.d/v1/metrics
  interval_secs: 10
  grace_period_secs: 60
  expiry_duration_secs: 900
  max_new_charts_per_request: 100

base_dir: /var/log/netdata/otel/v2

remote_storage:
  enabled: false
  uri: "fs:///var/log/netdata/otel/v2/remote"
  read_cache_max_size: "1GB"

auth:
  enabled: false

logs:
  rotation:
    default:
      max_file_size: "25MB"
      max_entries: 50000
  retention:
    default:
      max_files: 100000
      max_total_size: "1GB"
      max_age: "7 days"

traces:
  rotation:
    default:
      max_file_size: "25MB"
      max_entries: 50000
  retention:
    default:
      max_files: 100000
      max_total_size: "1GB"
      max_age: "7 days"
```

Stable v2.11.x ships the same file without the `traces:` section. Agents
before v2.11.0 used a different `logs:` schema (`size_of_journal_file`,
`store_otlp_json`, and similar); those keys now stop the plugin at
startup. `logs.journal_dir` is still accepted, only to locate the former
plugin's read-only journals.

## Minimal user override

Only write the fields you are changing. Omitted fields keep their stock
values. Parsing is strict: an unknown field, a malformed value, a
`traces:` section on an Agent without trace support, or a conflicting
combination (such as a TLS certificate without its key) stops the plugin
from starting.

```yaml
# /etc/netdata/otel.yaml
endpoint:
  path: "0.0.0.0:4317"
```

Edit via:

```bash
cd /etc/netdata 2>/dev/null || cd /opt/netdata/etc/netdata
sudo ./edit-config otel.yaml
```

## Bind address choices

| Bind address | Who can send OTLP |
|---|---|
| `127.0.0.1:4317` | Same-host clients only (stock default). |
| `0.0.0.0:4317` | Anyone who can reach the host on port 4317. Gate at the firewall. |
| `10.0.0.5:4317` | Clients on that interface only. |
| `[::]:4317` | IPv6 wildcard. |

The plugin validates that the bind string contains a colon, but does not
validate IP format; a typo like `0.0.0.0.4317` fails at socket-bind time with
a log line rather than a config-load error.

## Environment variable override

Any config option can be overridden at process launch. The env var name is
`NETDATA_OTEL_CFG_` plus the dotted path in uppercase with dots turned into
underscores. For `default` rotation and retention entries, drop the
`default` segment (`traces.retention.default.max_age` becomes
`NETDATA_OTEL_CFG_TRACES_RETENTION_MAX_AGE`). Unknown `NETDATA_OTEL_CFG_*`
variables stop the plugin. Agents before v2.11.0 used the `NETDATA_OTEL_`
prefix.

```bash
# One-shot: make the receiver listen on a nonstandard port without editing
# otel.yaml.
sudo systemctl set-environment NETDATA_OTEL_CFG_ENDPOINT_PATH=0.0.0.0:4319
sudo systemctl restart netdata
```

Env vars have the highest priority: stock config, then user config, then env.

## Restart and verify

```bash
sudo systemctl restart netdata
pgrep -a otel-plugin
ss -tlnp | grep 4317
```

If `ss` shows no listener on 4317 after restart, inspect:

```bash
sudo journalctl SYSLOG_IDENTIFIER=otel-plugin \
  SYSLOG_IDENTIFIER=otel-plugin/ingestor --since "-10 min"
```

Typical first-boot errors: bind permission denied on a privileged port,
address already in use, invalid bind string, or a strict-parsing
error on `otel.yaml`.
