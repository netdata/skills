# Enable the OTLP/gRPC receiver

## Scope

Bring the `otel-plugin` online and accept OTLP/gRPC traffic on a specific
network endpoint. Covers the stock defaults, minimal user override, bind
address choices, and restart flow.

## Default behavior

Out of the box, the plugin listens on `127.0.0.1:4317` (gRPC only). Metrics
and logs are both accepted on the same port. No trace receiver exists.

Stock settings, reproduced from the shipped `otel.yaml`:

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

logs:
  journal_dir: /var/log/netdata/otel/v1
  size_of_journal_file: "100MB"
  entries_of_journal_file: 50000
  duration_of_journal_file: "2 hours"
  number_of_journal_files: 10
  size_of_journal_files: "1GB"
  duration_of_journal_files: "7 days"
  store_otlp_json: false
```

## Minimal user override

Only write the fields you are changing. Unknown fields are ignored at the
top-level config for forward compatibility, but mapping files use strict
parsing (see `metric-mapping.md`).

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
`NETDATA_OTEL_` plus the dotted path in uppercase with dots turned into
underscores.

```bash
# One-shot: make the receiver listen on a nonstandard port without editing
# otel.yaml.
sudo systemctl set-environment NETDATA_OTEL_ENDPOINT_PATH=0.0.0.0:4319
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
sudo journalctl -u netdata --since "1 minute ago" | grep -i otel
```

Typical first-boot errors: bind permission denied on a privileged port,
address already in use, or invalid bind string.
