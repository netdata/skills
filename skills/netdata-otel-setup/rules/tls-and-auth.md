# TLS and auth on the OTLP receiver

## Scope

Terminating TLS at the Netdata `otel-plugin` receiver, optionally requiring
client certificates for mutual TLS. The plugin does not offer any
application-layer auth (no bearer tokens, no basic auth, no API keys on
the OTLP endpoint). Restricting who can send data means: bind address +
firewall, or mTLS.

## Server-side TLS

Provide a cert and key. TLS turns on as soon as both fields are set.

```yaml
endpoint:
  path: "0.0.0.0:4317"
  tls_cert_path: /etc/netdata/ssl/otel-cert.pem
  tls_key_path: /etc/netdata/ssl/otel-key.pem
```

Both files must be readable by the `netdata` user. A common failure is a
key with `0600 root:root` permissions after copying from `/etc/letsencrypt`.
Change ownership or symlink as appropriate.

## mTLS (client certificate required)

Add a CA certificate. The server then rejects TLS handshakes unless the
client presents a cert signed by that CA.

```yaml
endpoint:
  path: "0.0.0.0:4317"
  tls_cert_path: /etc/netdata/ssl/otel-cert.pem
  tls_key_path: /etc/netdata/ssl/otel-key.pem
  tls_ca_cert_path: /etc/netdata/ssl/client-ca.pem
```

`tls_ca_cert_path` only has an effect when `tls_cert_path` and
`tls_key_path` are also set.

## Producer-side (OTel Collector exporter)

Matching config on the sending side:

```yaml
exporters:
  otlp/netdata:
    endpoint: netdata.example.internal:4317
    tls:
      ca_file: /etc/otelcol/netdata-ca.pem
      cert_file: /etc/otelcol/client-cert.pem     # omit for server-only TLS
      key_file: /etc/otelcol/client-key.pem       # omit for server-only TLS
```

Without the Collector, an SDK-level exporter accepts the same parameters.
See the instrumentation skill for per-language examples.

## Permissions checklist

```bash
ls -l /etc/netdata/ssl/
# -r--r----- 1 root netdata  otel-cert.pem
# -r--r----- 1 root netdata  otel-key.pem
# -r--r----- 1 root netdata  client-ca.pem

sudo -u netdata cat /etc/netdata/ssl/otel-key.pem > /dev/null
# must return without error
```

If the plugin fails to load the key at startup, the journal shows a line
starting with `otel-plugin`:

```bash
sudo journalctl -u netdata --since "2 minutes ago" | grep otel-plugin
```

## Rotation

Certificates are loaded once at startup. On renewal, restart Netdata:

```bash
sudo systemctl restart netdata
```

There is no SIGHUP-based hot reload for the OTLP certs.

## Tenant selection (logs and traces)

With `auth.enabled: true` (v2.11.0+), senders must set the
`X-Scope-OrgID` gRPC header. Its value selects the tenant that owns the
log records and spans, and keys per-tenant retention entries under
`logs:` and `traces:`. Metrics are not tenant-scoped.

```yaml
auth:
  enabled: true
```

This is tenant selection, not authentication. Anyone who can reach the
port can claim any tenant, so trust the header only behind TLS or mTLS
and network controls. With `auth.enabled: false`, all logs and traces
belong to the `default` tenant.

## What you cannot do

- There is no way to require a bearer token on the OTLP endpoint. The
  `X-Scope-OrgID` header selects a tenant; it does not authenticate.
- There is no built-in per-tenant quota or rate limiting on incoming OTLP.
- There is no way to route different producers to different chart configs
  based on auth identity. All producers share the same mapping dir.

If those constraints matter, terminate TLS at an OTel Collector, apply
auth/rate limits there, and forward cleaned OTLP to Netdata over an
internal network. See `skills/netdata-collector-config/`.
