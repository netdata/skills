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
   ss -tlnp | grep 4317
   ```

   If unbound, the plugin crashed during init. Look for "address already
   in use", "permission denied", or an invalid bind string in the journal.

3. **Is the client hitting the right host and protocol?**

   OTLP/gRPC only. OTLP/HTTP (port 4318) is not accepted. Confirm with a
   quick TLS-off gRPC probe:

   ```bash
   grpcurl -plaintext -d '{}' <HOST>:4317 list
   ```

   A `Unimplemented` or method-specific response confirms gRPC is alive.
   `Connection refused` means the port is not open from where you are.

4. **Does anything arrive?**

   Turn on raw OTLP capture on logs (temporarily):

   ```yaml
   logs:
     store_otlp_json: true
   ```

   Send one request. Read the journal:

   ```bash
   sudo journalctl -D /var/log/netdata/otel/v1 -n 5 --output=json
   ```

   If nothing appears, the request did not reach the plugin at all (it
   was rejected at the network layer or the client had a different
   endpoint).

5. **Does the metric render?**

   ```bash
   curl -s 'http://localhost:19999/api/v2/contexts' | jq '.contexts | keys[]'
   ```

   Your metric name should appear. If the producer uses dots in the metric
   name, those survive as-is in the context key.

## Common symptoms

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

### "TLS handshake fails"

Three likely causes:

- Cert/key not readable by the `netdata` user.
- Hostname mismatch. The producer is connecting to an address not on the
  cert's SAN list.
- Producer sending HTTP to a TLS-enabled port. Send TLS or disable it.

### "mTLS accepts everyone"

`tls_ca_cert_path` requires both `tls_cert_path` and `tls_key_path` to
also be set. Setting the CA alone does nothing.

### "Env-var override has no effect"

The prefix is case-sensitive and the value must not be empty. Check:

```bash
sudo systemctl show netdata | grep NETDATA_OTEL
```

If not listed, `systemctl set-environment` was run in a different
context, or the systemd unit drops environment.

## Escalation data to capture

When filing a bug or asking a human for help, collect:

```bash
netdata -v
pgrep -a otel-plugin
ss -tlnp | grep 4317
sudo journalctl -u netdata --since "10 minutes ago" > /tmp/netdata.log
ls -l /etc/netdata/otel.yaml /etc/netdata/otel.d/v1/metrics/
```

Include the minimum OTLP producer config that reproduces the issue.
