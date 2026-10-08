---
name: netdata-otel-setup
description: Use when enabling the Netdata otel.plugin, writing /etc/netdata/otel.yaml, defining metric-to-chart mappings, configuring TLS on the OTLP receiver, setting log or trace retention, or debugging OTLP ingestion issues with Netdata. Covers OTLP gRPC and HTTP ingestion for metrics (v2.7.0+), logs (v2.9.0+, current storage schema v2.11.0+), and traces (nightly builds after v2.11.1; not in stable v2.11.x).
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
  - traces
---

# Netdata OTel setup

This skill configures Netdata's built-in `otel.plugin` to receive OpenTelemetry
data from collectors, SDKs, or instrumented applications over OTLP/gRPC or
OTLP/HTTP.

## When to use this skill

- The user wants Netdata to ingest metrics, logs, or traces sent via OTLP.
- The user is editing `otel.yaml` or placing files in `/etc/netdata/otel.d/`.
- An OTLP client reports that it cannot connect to the Netdata endpoint.
- Metrics arrive but render as generic unmapped charts and the user wants
  named dimensions.
- The user needs to turn on TLS on the OTLP receiver, or enable mTLS with a
  client CA.
- The user is sizing log or trace retention, or offloading them to object
  storage.

## Key facts

- Plugin: `otel-plugin` binary (Rust); `otel.plugin` is the logical integration id on the dashboard.
- Platform support: Linux and macOS. Windows and FreeBSD are not supported.
- Transport: OTLP over gRPC (port 4317, on by default) or HTTP (port 4318,
  once `receivers.otlp.protocols.http.enabled: true`). Both listen on
  `127.0.0.1` by default and accept metrics, logs, and traces. OTLP/HTTP
  serves `/v1/metrics`, `/v1/logs`, and `/v1/traces`.
- Listeners: `receivers.otlp.protocols.grpc` and `.http`, each with its own
  `enabled`, `endpoint`, and `tls` (`cert_file`, `key_file`,
  `client_ca_file`). Bind to `0.0.0.0` to accept remote traffic. At least
  one listener must stay enabled.
- Older files set the gRPC listener in an `endpoint:` section (`path`,
  `tls_cert_path`, `tls_key_path`, `tls_ca_cert_path`). Those names still
  work and log a deprecation warning; a value under `receivers:` wins when
  a file sets both.
- Receiver-format check: an Agent whose stock `otel.yaml` has only an
  `endpoint:` section has no OTLP/HTTP listener, and its plugin stops at
  startup on a `receivers:` section. There, configure gRPC under
  `endpoint:` and send gRPC to port 4317. Step 3 runs the check.
- Signals accepted, by Agent version:
  - Metrics: v2.7.0 and later.
  - Logs: v2.9.0 and later. v2.11.0 replaced the journal-file store with an
    indexed store and a new `otel.yaml` schema.
  - Traces: Netdata builds from `master` after 2026-08-17 (nightly), and the
    first stable release after v2.11.1. Stable v2.11.x has no trace
    receiver. See [`rules/trace-ingestion.md`](./rules/trace-ingestion.md)
    for the version check.
- Config file: `otel.yaml` inside the Netdata config directory (usually
  `/etc/netdata/otel.yaml` for native packages, or
  `/opt/netdata/etc/netdata/otel.yaml` for static installs). Edit via
  `sudo ./edit-config otel.yaml` from the config directory. The stock copy
  lives in `/usr/lib/netdata/conf.d/otel.yaml`.
- Parsing is strict (v2.11.0+). Unknown fields, malformed values, and keys
  from the former schema (`size_of_journal_file`, `number_of_journal_files`,
  `store_otlp_json`, and similar) stop the plugin from starting.
  `logs.journal_dir` is still accepted, only to locate the former
  plugin's read-only journals.
- Env-var overrides: `NETDATA_OTEL_CFG_` plus the option path in uppercase
  with dots replaced by underscores. Example:
  `receivers.otlp.protocols.http.enabled` becomes
  `NETDATA_OTEL_CFG_RECEIVERS_OTLP_PROTOCOLS_HTTP_ENABLED`. For `default`
  rotation and retention entries, drop the `default` segment:
  `traces.retention.default.max_age` becomes
  `NETDATA_OTEL_CFG_TRACES_RETENTION_MAX_AGE`. Env vars have the highest
  priority. Agents before v2.11.0 used the `NETDATA_OTEL_` prefix.
- Metric mapping directory: `/etc/netdata/otel.d/v1/metrics/`. Each YAML file
  can contain multiple mappings keyed by OTLP metric name. User files take
  priority over stock mappings.
- Chart layout is controlled by mapping files via `dimension_attribute_key`,
  not by OTLP attributes emitted by the producer. Set the attribute on the
  data point in your producer, then name that attribute in the mapping file.
- Logs and traces are stored under `base_dir` (default
  `/var/log/netdata/otel/v2`), one subtree per signal. Each signal has its
  own `rotation` and `retention` section (defaults: 1GB or 7 days,
  whichever comes first). `remote_storage` (S3 or filesystem offload) and
  `auth` (tenant selection via `X-Scope-OrgID`) are shared by logs and
  traces.
- Logs are explored in the Logs tab (`otel-logs` source); traces in the
  Traces tab (`otel-traces` Function). Both views require a signed-in
  Netdata Cloud user of the Agent's Space. The data stays on the Agent.
- The plugin automatically expires charts with no incoming data after
  `metrics.expiry_duration_secs` (default 900s).

## Step-by-step

1. Verify the Netdata version supports the signals you need.

   ```bash
   netdata -v
   # v2.7.0+ for metrics, v2.9.0+ for logs (v2.11.0+ for the schema below).
   # Traces: the stock config must contain a traces section.
   grep -c '^traces:' /usr/lib/netdata/conf.d/otel.yaml \
     /opt/netdata/usr/lib/netdata/conf.d/otel.yaml 2>/dev/null
   ```

   A count of `0` (or no file) means the Agent cannot receive traces.
   Route traces elsewhere, or move the Agent to a nightly build.

2. Open the config file with `edit-config` (this preserves permissions and
   copies from the stock template).

   ```bash
   cd /etc/netdata 2>/dev/null || cd /opt/netdata/etc/netdata
   sudo ./edit-config otel.yaml
   ```

3. Check the receiver format, then set the listeners. Read the Agent's
   stock `otel.yaml`, not the user copy:

   ```bash
   grep -E '^(receivers|endpoint):' /usr/lib/netdata/conf.d/otel.yaml \
     /opt/netdata/usr/lib/netdata/conf.d/otel.yaml 2>/dev/null
   # Docker: docker exec netdata grep -E '^(receivers|endpoint):' \
   #   /usr/lib/netdata/conf.d/otel.yaml
   ```

   Only `endpoint:` means the Agent has no OTLP/HTTP listener: configure
   gRPC under `endpoint:` and send gRPC to port 4317 (example in
   [`rules/enable-otlp-receiver.md`](./rules/enable-otlp-receiver.md)).
   With `receivers:`, leave the defaults for local-only gRPC traffic, turn
   on the OTLP/HTTP listener when senders use OTLP/HTTP, and for remote
   OTLP clients bind on `0.0.0.0` and protect each port (TLS, firewall).

   ```yaml
   receivers:
     otlp:
       protocols:
         grpc:
           endpoint: "0.0.0.0:4317"
         http:
           enabled: true
           endpoint: "0.0.0.0:4318"
   ```

4. Logs and traces ingestion are always on. Change retention only when the
   defaults are wrong for the volume. A user file needs only the fields
   that change.

   ```yaml
   logs:
     retention:
       default:
         max_total_size: "10GB"
         max_age: "30 days"
   traces:
     retention:
       default:
         max_total_size: "10GB"
         max_age: "30 days"
   ```

   Omit the `traces:` block on an Agent without trace support; strict
   parsing rejects it there.

5. Restart Netdata to pick up changes.

   ```bash
   sudo systemctl restart netdata
   ```

6. Confirm the plugin is listening.

   ```bash
   ss -tlnp | grep -E '4317|4318'
   # Expect one listener per enabled protocol, on the address you configured.
   ```

7. Send a test metric from an OTLP client and watch it appear on the
   Netdata dashboard at `http://HOST:19999`. For traces, send spans and
   open the Traces tab. See the MCP integration skill for programmatic
   verification.

8. If the metric renders with unhelpful dimension names, add a mapping file.
   See [`rules/metric-mapping.md`](./rules/metric-mapping.md).

## Common mistakes

- Pointing an OTLP/HTTP client at an Agent whose OTLP/HTTP listener is off
  (the default). Many SDKs default to `http/protobuf`: turn the listener on
  and send to port 4318, or set `OTEL_EXPORTER_OTLP_PROTOCOL=grpc` and send
  to port 4317. A protocol sent to the other protocol's port fails.
- Sending traces to a stable v2.11.x Agent. It has no trace receiver.
  Check for trace support first (step 1).
- Copying an `otel.yaml` written for v2.10 or earlier. Keys such as
  `size_of_journal_file`, `number_of_journal_files`, and `store_otlp_json` stop
  the v2.11.0+ plugin at startup. Rebuild the file from the current stock
  config.
- Expecting `logs.retention` to also bound traces. Traces have their own
  `traces.retention` section.
- Treating `retention.*.max_total_size` as a disk cap. Write-ahead logs,
  catalogs, and the remote-read cache are additional.
- Binding to `0.0.0.0` without also considering firewall rules. A public
  `4317` or `4318` is a denial-of-service target. Gate it at the host
  firewall.
- Editing `otel.yaml` directly inside `/usr/lib/netdata` or similar stock
  paths. Stock configs get overwritten on upgrade. Always use the
  user-level config directory via `edit-config`.
- Mapping files with instrumentation-scope regexes that do not match the
  actual scope name. Verify the scope before writing a mapping by sending
  the same data through a Collector `debug` exporter with
  `verbosity: detailed`.
- Unknown fields in a mapping file. The plugin parses mapping files with
  `deny_unknown_fields`, so a typo in `dimesion_attribute_key` (note the
  typo) causes the whole file to be skipped and logs an error.
- Expecting env vars without the `NETDATA_OTEL_CFG_` prefix to override
  config on v2.11.0+.

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

A non-empty match confirms end-to-end ingestion. For a trace smoke test,
see [`rules/trace-ingestion.md`](./rules/trace-ingestion.md). For the
canonical end-to-end fixture, see [`tests/e2e/`](../../tests/e2e/) in this
repo.

## References

- [`rules/enable-otlp-receiver.md`](./rules/enable-otlp-receiver.md)
- [`rules/metric-mapping.md`](./rules/metric-mapping.md)
- [`rules/log-ingestion.md`](./rules/log-ingestion.md)
- [`rules/trace-ingestion.md`](./rules/trace-ingestion.md)
- [`rules/tls-and-auth.md`](./rules/tls-and-auth.md)
- [`rules/troubleshooting.md`](./rules/troubleshooting.md)
- Netdata integration doc: https://learn.netdata.cloud/docs/collecting-metrics/opentelemetry
- Netdata source: `src/crates/otel-plugin/integrations/opentelemetry.md`
  and `src/crates/otel-plugin/configs/otel.yaml.in` in the Netdata repo.
- Netdata docs: `docs/opentelemetry/otlp-ingestion.md`,
  `docs/opentelemetry/securing-the-otlp-endpoint.md`,
  `docs/opentelemetry/trace-storage-and-retention.md`,
  `docs/logs/log-storage-and-retention.md` in the Netdata repo.
