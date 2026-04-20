---
name: netdata-otel-setup
description: Use when enabling the Netdata otel.plugin, writing /etc/netdata/otel.yaml, defining metric-to-chart mappings, configuring TLS on the OTLP receiver, or debugging OTLP ingestion issues with Netdata. Covers OTLP gRPC ingestion for metrics (v2.7.0+) and logs (v2.9.0+). Traces are not yet supported.
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - opentelemetry
  - otel
  - otlp
  - setup
  - metrics
  - logs
---

# Netdata OTel setup

This skill configures Netdata's built-in `otel.plugin` to receive OpenTelemetry
data from collectors, SDKs, or instrumented applications over OTLP/gRPC.

## When to use this skill

- The user wants Netdata to ingest metrics or logs sent via OTLP.
- The user is editing `otel.yaml` or placing files in `/etc/netdata/otel.d/`.
- An OTLP client reports that it cannot connect to the Netdata endpoint.
- Metrics arrive but render as generic unmapped charts and the user wants
  named dimensions.
- The user needs to turn on TLS on the OTLP receiver, or enable mTLS with a
  client CA.
- The user is debugging log ingestion and journal rotation.

## Key facts

- Plugin: `otel-plugin` binary (Rust); `otel.plugin` is the logical integration id on the dashboard.
- Platform support: Linux only. Windows is not supported by the plugin.
- Transport: **OTLP/gRPC only** on the configured endpoint. OTLP/HTTP
  (port 4318) is not accepted.
- Default endpoint: `127.0.0.1:4317`. Bind to `0.0.0.0:4317` to accept remote
  traffic. Configurable via `endpoint.path`.
- Signals accepted: metrics (stable since v2.7.0) and logs (stable since
  v2.9.0). Traces are not yet accepted.
- Config file: `otel.yaml` inside the Netdata config directory (usually
  `/etc/netdata/otel.yaml` for native packages, or
  `/opt/netdata/etc/netdata/otel.yaml` for static installs). Edit via
  `sudo ./edit-config otel.yaml` from the config directory.
- Env-var overrides: any config option can be overridden by an environment
  variable named `NETDATA_OTEL_` plus the option path in uppercase with dots
  replaced by underscores. Example: `endpoint.tls_cert_path` becomes
  `NETDATA_OTEL_ENDPOINT_TLS_CERT_PATH`. Env vars have the highest priority.
- Metric mapping directory: `/etc/netdata/otel.d/v1/metrics/`. Each YAML file
  can contain multiple mappings keyed by OTLP metric name. User files take
  priority over stock mappings.
- Chart layout is controlled by mapping files via `dimension_attribute_key`,
  not by OTLP attributes emitted by the producer. Set the attribute on the
  data point in your producer, then name that attribute in the mapping file.
- Logs default journal dir is `/var/log/netdata/otel/v1`. Override with
  `logs.journal_dir` if the `netdata` user cannot write there.
- The plugin automatically expires charts with no incoming data after
  `metrics.expiry_duration_secs` (default 900s).

## Step-by-step

1. Verify Netdata version is recent enough.

   ```bash
   netdata -v
   # Expect v2.7.0 or later for metrics, v2.9.0 or later for logs.
   ```

2. Open the config file with `edit-config` (this preserves permissions and
   copies from the stock template).

   ```bash
   cd /etc/netdata 2>/dev/null || cd /opt/netdata/etc/netdata
   sudo ./edit-config otel.yaml
   ```

3. Set the endpoint. For local-only traffic, leave the default. For remote
   OTLP clients, bind on `0.0.0.0`.

   ```yaml
   endpoint:
     path: "0.0.0.0:4317"
   ```

4. Logs ingestion is always on. The default journal directory is
   `/var/log/netdata/otel/v1`. Override only if the default is unsuitable.

   ```yaml
   logs:
     journal_dir: /var/log/netdata/otel/v1
   ```

5. Restart Netdata to pick up changes.

   ```bash
   sudo systemctl restart netdata
   ```

6. Confirm the plugin is listening.

   ```bash
   ss -tlnp | grep 4317
   # Expect a listener on the address you configured.
   ```

7. Send a test metric from an OTLP client and watch it appear on the
   Netdata dashboard at `http://HOST:19999`. See the MCP integration skill
   for programmatic verification.

8. If the metric renders with unhelpful dimension names, add a mapping file.
   See [`rules/metric-mapping.md`](./rules/metric-mapping.md).

## Common mistakes

- Pointing an OTLP/HTTP client at the Netdata endpoint. The plugin does not
  accept OTLP/HTTP yet. Use gRPC.
- Trying to send traces. Netdata does not yet accept trace signals. Route
  traces to a dedicated backend (Jaeger, Tempo, or an external SaaS) until
  trace support lands.
- Binding to `0.0.0.0` without also considering firewall rules. A public
  `4317` is a denial-of-service target. Gate it at the host firewall.
- Editing `otel.yaml` directly inside `/usr/lib/netdata` or similar stock
  paths. Stock configs get overwritten on upgrade. Always use the
  user-level config directory via `edit-config`.
- Setting `logs.journal_dir` to a path the `netdata` user cannot write to.
  Pick a writable path or keep the default.
- Mapping files with instrumentation-scope regexes that do not match the
  actual scope name. Verify the scope before writing a mapping by looking
  at the raw OTLP envelope (enable `logs.store_otlp_json: true` while
  debugging).
- Unknown fields in a mapping file. The plugin parses mapping files with
  `deny_unknown_fields`, so a typo in `dimesion_attribute_key` (note the
  typo) causes the whole file to fall back to defaults and logs an error.
- Expecting env vars without the `NETDATA_OTEL_` prefix to override config.
  The prefix is required.

## Verification

Run the following from the Netdata host after restart.

```bash
# Plugin process is running.
pgrep -a otel-plugin

# gRPC port is bound.
ss -tlnp | grep 4317

# Send a one-off OTLP metric with grpcurl for a smoke test.
grpcurl -plaintext -d '{
  "resourceMetrics": [{
    "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "smoketest"}}]},
    "scopeMetrics": [{
      "scope": {"name": "smoketest.scope"},
      "metrics": [{
        "name": "smoketest.counter",
        "sum": {
          "dataPoints": [{"asInt": 1, "timeUnixNano": "'$(date +%s)000000000'"}],
          "aggregationTemporality": 2,
          "isMonotonic": true
        }
      }]
    }]
  }]
}' localhost:4317 opentelemetry.proto.collector.metrics.v1.MetricsService/Export
```

Then confirm the metric arrived:

```bash
curl -s 'http://localhost:19999/api/v2/contexts' | jq '.contexts | keys[]' | grep smoketest
```

A non-empty match confirms end-to-end ingestion. For the canonical
end-to-end fixture, see [`tests/e2e/`](../../tests/e2e/) in this repo.

## References

- [`rules/enable-otlp-receiver.md`](./rules/enable-otlp-receiver.md)
- [`rules/metric-mapping.md`](./rules/metric-mapping.md)
- [`rules/log-ingestion.md`](./rules/log-ingestion.md)
- [`rules/tls-and-auth.md`](./rules/tls-and-auth.md)
- [`rules/troubleshooting.md`](./rules/troubleshooting.md)
- Netdata integration doc: https://learn.netdata.cloud/docs/collecting-metrics/opentelemetry
- Netdata source: `src/crates/netdata-otel/otel-plugin/integrations/opentelemetry.md` in the Netdata repo.
