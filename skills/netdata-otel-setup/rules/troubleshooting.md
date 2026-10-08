# Troubleshooting OTLP ingestion

## Fast triage ladder

1. **Is the plugin running?**

   ```bash
   pgrep -a otel-plugin
   ```

   If empty, Netdata did not start the plugin. Check the journal:

   ```bash
   sudo journalctl -u netdata --since "2 minutes ago" | grep -i otel
   ```

2. **Is the port bound?**

   ```bash
   ss -tlnp | grep -E '4317|4318'
   ```

   Port 4318 appears only with the OTLP/HTTP listener on. If an enabled
   listener is unbound, the plugin crashed during init. Look for
   "address already in use", "permission denied", an invalid bind string,
   or a strict `otel.yaml` parsing error in the journal. Keys from the v2.10 schema
   (`size_of_journal_file`, `store_otlp_json`, and similar) are a common cause
   after an upgrade.

3. **Is the client hitting the right host and protocol?**

   gRPC goes to port 4317. OTLP/HTTP goes to port 4318 and needs
   `receivers.otlp.protocols.http.enabled: true`; its exporters post to
   `/v1/metrics`, `/v1/logs`, and `/v1/traces`. Confirm the gRPC listener
   with a quick TLS-off probe:

   ```bash
   grpcurl -plaintext -d '{}' <HOST>:4317 list
   ```

   The plugin does not enable server reflection, so `list` returns an
   error rather than service names; any gRPC error still confirms gRPC is
   alive. `Connection refused` means the port is not open from where you
   are.

4. **Does anything arrive?**

   Read the plugin's own log lines. Rejected exports (bad timestamps,
   strict-parsing errors, chart budget overruns) are logged there:

   ```bash
   sudo journalctl SYSLOG_IDENTIFIER=otel-plugin \
     SYSLOG_IDENTIFIER=otel-plugin/ingestor --since "-10 min"
   ```

   To see the exact payload a producer sends, route it through an OTel
   Collector with a `debug` exporter (`verbosity: detailed`). The plugin
   has no raw-payload capture since v2.11.0.

5. **Does the metric render?**

   ```bash
   curl -s 'http://localhost:19999/api/v2/contexts' | jq '.contexts | keys[]'
   ```

   Your metric name should appear. If the producer uses dots in the metric
   name, those survive as-is in the context key.

## Common symptoms

### "unknown field `receivers`" at startup

The Agent predates the `receivers:` format; its stock `otel.yaml` has
only an `endpoint:` section (see the check in `enable-otlp-receiver.md`).
Move the gRPC listener settings under `endpoint:` (`path`,
`tls_cert_path`, `tls_key_path`, `tls_ca_cert_path`) and send gRPC to
port 4317; this Agent has no OTLP/HTTP listener. The error
`unrecognized environment variable: NETDATA_OTEL_CFG_RECEIVERS_...` has
the same cause: use the `NETDATA_OTEL_CFG_ENDPOINT_*` names.

### "No charts appear for my metric"

Usually one of:

- Metric name mismatch between producer and mapping file (the mapping key
  is an exact string, not a regex).
- Mapping file has an unknown field and failed to load. Look for an error
  line in the journal: `otel-plugin ... failed to parse chart config`.
- The metric arrived but `metrics.expiry_duration_secs` (default 900s)
  expired it between sends. For test metrics, send at least once per 15
  minutes or lower the expiry.

### "Charts appear but dimensions are unhelpful"

No mapping for this metric yet. Add a file under
`/etc/netdata/otel.d/v1/metrics/` with a `dimension_attribute_key`. See
`metric-mapping.md`.

### "I see charts but they flap"

`metrics.grace_period_secs` (default 60s) may be too short for the
producer's actual emit cadence. If your producer emits every 30s but the
network is lossy, bump grace. If your producer's interval is 60s+, set
`interval_secs` per metric to match.

### "Spans are missing from the Traces tab"

Usually one of:

- The Agent has no trace receiver. Stable v2.11.x and older do not
  accept traces; see `trace-ingestion.md` for the version check.
- The SDK's protocol and port do not match. `http/protobuf` needs port
  4318 with the OTLP/HTTP listener on; `grpc` needs port 4317.
- The SDK trace exporter is still `none`
  (`OTEL_TRACES_EXPORTER=none`), a leftover from before trace support.
- The spans fall outside the accepted window: started more than 24 hours
  ago or end more than 10 minutes in the future. The Agent journal logs a
  warning for rejected spans.
- `auth.enabled: true` and the viewer is looking at the `default` tenant
  while the sender set a different `X-Scope-OrgID`.
- The viewer is not signed in to Netdata Cloud. The Traces tab requires
  a signed-in user of the Agent's Space.

### "TLS handshake fails"

Three likely causes:

- Cert/key not readable by the `netdata` user.
- Hostname mismatch. The producer is connecting to an address not on the
  cert's SAN list.
- Producer sending plaintext (`http://`) to a TLS-enabled listener. Send
  TLS (`https://`) or disable it.

### "mTLS accepts everyone"

TLS settings are per listener. mTLS on the gRPC listener does not protect
an OTLP/HTTP listener without its own `tls.client_ca_file`. Give every
enabled listener the CA, or turn off the one no sender uses.

`tls.client_ca_file` requires `tls.cert_file` and `tls.key_file` on the
same listener. Setting the CA alone stops the plugin from starting.

### "Env-var override has no effect"

The prefix is case-sensitive and the value must not be empty. Check:

```bash
sudo systemctl show netdata | grep NETDATA_OTEL_CFG
```

On v2.11.0+ the prefix is `NETDATA_OTEL_CFG_`; the older `NETDATA_OTEL_`
names are not read. An unknown `NETDATA_OTEL_CFG_*` variable stops the
plugin.

If not listed, `systemctl set-environment` was run in a different
context, or the systemd unit drops environment.

## Escalation data to capture

When filing a bug or asking a human for help, collect:

```bash
netdata -v
pgrep -a otel-plugin
ss -tlnp | grep -E '4317|4318'
sudo journalctl -u netdata --since "10 minutes ago" > /tmp/netdata.log
ls -l /etc/netdata/otel.yaml /etc/netdata/otel.d/v1/metrics/
```

Include the minimum OTLP producer config that reproduces the issue.
