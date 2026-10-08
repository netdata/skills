# Enable the OTLP receiver

## Scope

Bring the `otel-plugin` online and accept OTLP/gRPC, OTLP/HTTP, or both on
specific network endpoints. Covers the receiver-format check, stock
defaults, minimal user override, bind address choices, and restart flow.

## Check the receiver format first

Before writing or editing receiver config, read the Agent's stock
`otel.yaml`, not the user copy. `edit-config` copies the stock file only
when no user copy exists, so a user copy can carry an older format.

```bash
# Native packages and static installs (/opt/netdata):
grep -E '^(receivers|endpoint):' /usr/lib/netdata/conf.d/otel.yaml \
  /opt/netdata/usr/lib/netdata/conf.d/otel.yaml 2>/dev/null
# Docker (container named netdata):
docker exec netdata grep -E '^(receivers|endpoint):' \
  /usr/lib/netdata/conf.d/otel.yaml
```

No output: find the stock directory with `sudo ./edit-config --help`, run
in the config directory.

- `receivers:`: use the listener format in this file.
- Only `endpoint:`: the Agent has no OTLP/HTTP listener. Configure the
  gRPC listener under `endpoint:` and point every sender at gRPC on port
  4317. The matching variables are `NETDATA_OTEL_CFG_ENDPOINT_PATH`,
  `NETDATA_OTEL_CFG_ENDPOINT_TLS_CERT_PATH`,
  `NETDATA_OTEL_CFG_ENDPOINT_TLS_KEY_PATH`, and
  `NETDATA_OTEL_CFG_ENDPOINT_TLS_CA_CERT_PATH`.

```yaml
endpoint:
  path: "0.0.0.0:4317"
  tls_cert_path: /etc/netdata/ssl/otel-cert.pem      # TLS needs cert and key
  tls_key_path: /etc/netdata/ssl/otel-key.pem
  tls_ca_cert_path: /etc/netdata/ssl/client-ca.pem   # optional: mTLS
```

Source: `system/edit-config` and `src/crates/otel-plugin/src/config/mod.rs`
(the plugin reads `$NETDATA_STOCK_CONFIG_DIR/otel.yaml`) in the Netdata
repo.

## Default behavior

Out of the box, the plugin listens for OTLP/gRPC on `127.0.0.1:4317`. The
OTLP/HTTP listener on `127.0.0.1:4318` is off until
`receivers.otlp.protocols.http.enabled: true`. Each listener accepts
metrics, logs, and traces. Traces need an Agent built from `master` after
2026-08-17 (nightly) or the first stable release after v2.11.1; stable
v2.11.x does not register a trace service.

Stock settings, reproduced from the shipped `otel.yaml` (comments removed;
Linux package paths):

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        enabled: true
        endpoint: "127.0.0.1:4317"
        tls:
          cert_file: null
          key_file: null
          client_ca_file: null
      http:
        enabled: false
        endpoint: "127.0.0.1:4318"
        tls:
          cert_file: null
          key_file: null
          client_ca_file: null

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

Older files configure the gRPC listener in an `endpoint:` section
(`path`, `tls_cert_path`, `tls_key_path`, `tls_ca_cert_path`). These names
still work and log a deprecation warning. If a file sets an option under
both names, the value under `receivers:` wins.

Stable v2.11.x ships an older stock file, without the `traces:` section. Agents
before v2.11.0 used a different `logs:` schema (`size_of_journal_file`,
`store_otlp_json`, and similar); those keys now stop the plugin at
startup. `logs.journal_dir` is still accepted, only to locate the former
plugin's read-only journals.

## Minimal user override

Only write the fields you are changing. Omitted fields keep their stock
values. Parsing is strict: an unknown field, a malformed value, a
`traces:` section on an Agent without trace support, or a conflicting
combination (such as a TLS certificate without its key, both listeners
disabled, or two enabled listeners claiming the same socket) stops the
plugin from starting.

```yaml
# /etc/netdata/otel.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: "0.0.0.0:4317"
```

To also receive OTLP/HTTP, turn on its listener:

```yaml
receivers:
  otlp:
    protocols:
      http:
        enabled: true
```

Turn off a listener that no sender uses (`enabled: false`).

Edit via:

```bash
cd /etc/netdata 2>/dev/null || cd /opt/netdata/etc/netdata
sudo ./edit-config otel.yaml
```

## Bind address choices

Each listener has its own `endpoint`. The forms below apply to both; the
OTLP/HTTP listener uses its own port (stock `127.0.0.1:4318`).

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
variables stop the plugin. The older `NETDATA_OTEL_CFG_ENDPOINT_*` names
still work and log a deprecation warning. Agents before v2.11.0 used the
`NETDATA_OTEL_` prefix.

```bash
# One-shot: make the gRPC listener use a nonstandard port without editing
# otel.yaml.
sudo systemctl set-environment NETDATA_OTEL_CFG_RECEIVERS_OTLP_PROTOCOLS_GRPC_ENDPOINT=0.0.0.0:4319
sudo systemctl restart netdata
```

Env vars have the highest priority: stock config, then user config, then env.

## Restart and verify

```bash
sudo systemctl restart netdata
pgrep -a otel-plugin
ss -tlnp | grep -E '4317|4318'
```

If `ss` shows no listener for an enabled protocol after restart, inspect:

```bash
sudo journalctl SYSLOG_IDENTIFIER=otel-plugin \
  SYSLOG_IDENTIFIER=otel-plugin/ingestor --since "-10 min"
```

Typical first-boot errors: bind permission denied on a privileged port,
address already in use (often a local OTel Collector on 4317 or 4318),
invalid bind string, or a strict-parsing error on `otel.yaml`.
