# Trace ingestion

## Scope

Receiving OpenTelemetry traces on the Netdata Agent: version support,
storage, retention, offloading, rejection rules, and how stored traces
are explored. Source: `docs/opentelemetry/trace-storage-and-retention.md`,
`docs/opentelemetry/otlp-ingestion.md`, and
`src/crates/otel-plugin/integrations/opentelemetry.md` in the Netdata
repo.

## Version support

Trace ingestion landed on Netdata `master` on 2026-08-17 (PR #23479). It
ships in nightly builds and in the first stable release after v2.11.1.
Stable v2.11.0 and v2.11.1 do not register the OTLP trace service, so
trace exports to them fail.

Check before configuring anything:

```bash
# Stock config path for native packages; static installs prefix /opt/netdata.
grep -c '^traces:' /usr/lib/netdata/conf.d/otel.yaml \
  /opt/netdata/usr/lib/netdata/conf.d/otel.yaml 2>/dev/null
```

A non-zero count means the Agent accepts traces. Otherwise, keep traces
on their current backend (or set the SDK trace exporter to `none`) until
the Agent is upgraded.

## How spans arrive

Traces use the same listeners as metrics and logs: OTLP/gRPC on
`127.0.0.1:4317`, and OTLP/HTTP on `127.0.0.1:4318` (path `/v1/traces`)
once `receivers.otlp.protocols.http.enabled: true`.

- **SDK:** set `OTEL_TRACES_EXPORTER=otlp`, then either
  `OTEL_EXPORTER_OTLP_PROTOCOL=grpc` with
  `OTEL_EXPORTER_OTLP_ENDPOINT=http://NETDATA_HOST:4317`, or
  `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf` with
  `OTEL_EXPORTER_OTLP_ENDPOINT=http://NETDATA_HOST:4318`. HTTP exporters
  append `/v1/traces` to that base endpoint.
- **Collector:** add the Netdata `otlp` (gRPC) or `otlphttp` exporter to a
  `traces` pipeline. See
  `skills/netdata-collector-config/rules/exporters-to-netdata.md`.

Set the `service.name` resource attribute in every application. It names
the service each span belongs to.

## Storage

Spans are stored under `base_dir` (default `/var/log/netdata/otel/v2`) in
its `traces/` subtree. Incoming spans go to a write-ahead log. At
`traces.rotation.default.max_file_size` (25MB),
`traces.rotation.default.max_entries` (50000 spans), or about 15 minutes
after its first span, the log is sealed into an indexed file. Each file
indexes span names, kinds, statuses, and span, resource, scope, event,
and link attributes, plus trace IDs for whole-trace lookup.

## Retention

| Option | Default | Meaning |
|---|---|---|
| `traces.retention.default.max_files` | `100000` | Maximum indexed files kept. |
| `traces.retention.default.max_total_size` | `1GB` | Maximum total size of indexed files kept. |
| `traces.retention.default.max_age` | `7 days` | Maximum file age, measured on the start of its newest span. |

Traces have their own settings, separate from `logs`. A user `otel.yaml`
needs only the fields that change:

```yaml
traces:
  retention:
    default:
      max_total_size: "20GB"
      max_age: "30 days"
```

Strict parsing rejects a `traces:` section on an Agent without trace
support. Remove it before downgrading to stable v2.11.x.

`max_total_size` is not a disk cap. The active write-ahead log, catalogs,
and the remote-read cache are additional. The 1GB default is usually
reached long before 7 days. To size it, run the senders for a day,
measure `du -sh <base_dir>/traces/index/`, and multiply by the days to
keep locally.

## Offloading to object storage

Traces share `remote_storage` and its download cache with logs. See
`log-ingestion.md` for the configuration. Trace-specific limits:

- A query that needs more offloaded data than the cache holds fails with
  a message to narrow the time range or raise
  `remote_storage.read_cache_max_size`. A search reads up to 24 hours
  beyond each side of its window to complete the traces it finds.
- A trace-ID lookup without a time range searches all retained data,
  local and offloaded, and fails once offloaded history exceeds the
  cache.
- An unreadable offloaded file marks the answer partial
  (`remote_unavailable`).

## Rejected spans

By default a span is rejected when it started more than 24 hours ago or
ends more than 10 minutes in the future. A span without an end time is
judged by its start. Rejections are reported through OTLP
`partial_success` (visibility depends on the sender) and logged as a
warning in the Agent journal. Check the sender's clock first.

## Tenants

With `auth.enabled: true`, senders must set the `X-Scope-OrgID` header
(gRPC metadata or HTTP header), and per-tenant retention entries are
keyed by its value. This is tenant selection, not authentication; trust
it only behind TLS or mTLS. With `auth.enabled: false`, all traces
belong to the `default` tenant.

## Exploring traces

Stored traces are explored in the dashboard's Traces tab, which queries
the Agent's `otel-traces` Function. The Function supports trace search,
lookup of one trace by ID, the slowest traces, a duration overview, and
attribute facets (`src/crates/otel-ledger/src/ledger/rpc/traces/wire.rs`
in the Netdata repo). Viewing requires a signed-in Netdata Cloud user of
the Agent's Space; trace data is not stored in Netdata Cloud.

The Function is marked as sensitive data and restricted to signed-in
users of the same Space. Whether an MCP client can call `otel-traces`
through `execute_function` is not verified.

## Smoke test

The plugin does not enable gRPC server reflection, so a bare `grpcurl`
call cannot discover the trace service. Use the OpenTelemetry
`telemetrygen` tool, which speaks OTLP/gRPC by default
(`cmd/telemetrygen` in `opentelemetry-collector-contrib`):

```bash
go install github.com/open-telemetry/opentelemetry-collector-contrib/cmd/telemetrygen@latest
telemetrygen traces --otlp-insecure --otlp-endpoint 127.0.0.1:4317 \
  --traces 1 --service smoketest
```

Open the Traces tab and look for service `smoketest`. An `Unimplemented`
error from `telemetrygen` indicates the Agent has no trace receiver (stable
v2.11.x or older).
