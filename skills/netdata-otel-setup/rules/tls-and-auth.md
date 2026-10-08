# TLS and auth on the OTLP receiver

## Scope

Terminating TLS at the Netdata `otel-plugin` receiver, optionally requiring
client certificates for mutual TLS. The plugin does not offer any
application-layer auth (no bearer tokens, no basic auth, no API keys on
the OTLP endpoint). Restricting who can send data means: bind address +
firewall, or mTLS.

## Check the receiver format first

Before writing TLS settings, read the Agent's stock `otel.yaml` (Docker
and other installs: see `enable-otlp-receiver.md`):

```bash
grep -E '^(receivers|endpoint):' /usr/lib/netdata/conf.d/otel.yaml \
  /opt/netdata/usr/lib/netdata/conf.d/otel.yaml 2>/dev/null
```

With `receivers:`, use the per-listener examples below. With only
`endpoint:`, the Agent has a single gRPC listener: set TLS with
`tls_cert_path`, `tls_key_path`, and `tls_ca_cert_path` (mTLS) under
`endpoint:`, as in the example in `enable-otlp-receiver.md`.

## Server-side TLS

Provide a cert and key. TLS turns on for a listener as soon as both of
its fields are set. Each listener (`grpc`, `http`) has its own `tls`
block; configure TLS on every listener that binds beyond loopback.

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: "0.0.0.0:4317"
        tls:
          cert_file: /etc/netdata/ssl/otel-cert.pem
          key_file: /etc/netdata/ssl/otel-key.pem
```

Both files must be readable by the `netdata` user. A common failure is a
key with `0600 root:root` permissions after copying from `/etc/letsencrypt`.
Change ownership or symlink as appropriate.

## mTLS (client certificate required)

Add a CA certificate. The listener then rejects TLS handshakes unless the
client presents a cert signed by that CA. With both listeners on, give
each one the CA:

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: "0.0.0.0:4317"
        tls:
          cert_file: /etc/netdata/ssl/otel-cert.pem
          key_file: /etc/netdata/ssl/otel-key.pem
          client_ca_file: /etc/netdata/ssl/client-ca.pem
      http:
        enabled: true
        endpoint: "0.0.0.0:4318"
        tls:
          cert_file: /etc/netdata/ssl/otel-cert.pem
          key_file: /etc/netdata/ssl/otel-key.pem
          client_ca_file: /etc/netdata/ssl/client-ca.pem
```

`client_ca_file` requires `cert_file` and `key_file` on the same
listener; setting it alone stops the plugin from starting. Older files
use `endpoint.tls_cert_path`, `endpoint.tls_key_path`, and
`endpoint.tls_ca_cert_path` for the gRPC listener; those names still work
and log a deprecation warning.

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

For the OTLP/HTTP listener, the Collector's `otlphttp` exporter takes the
same `tls` block with an `https://` endpoint on port 4318.

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
`X-Scope-OrgID` header: gRPC metadata on the gRPC listener, an HTTP
header on the OTLP/HTTP listener. Its value selects the tenant that owns
the log records and spans, and keys per-tenant retention entries under
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
