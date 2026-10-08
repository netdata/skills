# Log ingestion

## Scope

OTLP log ingestion is always on once `otel-plugin` is running. Logs arrive
on the gRPC listener and, when it is on, the OTLP/HTTP listener
(`/v1/logs`). This rule covers the log store used by v2.11.0 and later:
storage layout, rotation, retention, offloading, and inspection. Traces
use a parallel store with separate settings; see `trace-ingestion.md`.

## Storage

Ingested log records are written under `base_dir` (default
`/var/log/netdata/otel/v2` on Linux packages), in its `logs/` subtree.
Incoming records are appended to a write-ahead log. When it reaches
`max_file_size`, `max_entries`, or about 15 minutes of age, it is sealed
into an indexed file and the write-ahead log is deleted. Every field is
indexed.

Agents before v2.11.0 wrote systemd-compatible journal files under
`/var/log/netdata/otel/v1` and were configured with `logs.journal_dir`
and `*_journal_file*` keys. The `*_journal_file*` keys and
`store_otlp_json` now stop the plugin at startup. The only accepted
legacy key is `logs.journal_dir`, used solely to locate
the former plugin's read-only journals.

Source: `docs/logs/log-storage-and-retention.md` and
`src/crates/otel-plugin/integrations/opentelemetry.md` in the Netdata repo.

## Rotation and retention

All knobs live in `otel.yaml` under `logs:`. Defaults:

| Field | Default | What it controls |
|---|---|---|
| `logs.rotation.default.max_file_size` | `25MB` | Write-ahead log size that triggers sealing. |
| `logs.rotation.default.max_entries` | `50000` | Write-ahead log entry count that triggers sealing. |
| `logs.retention.default.max_files` | `100000` | Maximum retained indexed files. |
| `logs.retention.default.max_total_size` | `1GB` | Maximum retained indexed-data size. |
| `logs.retention.default.max_age` | `7 days` | Maximum age of an indexed file, measured on its newest entry. |

Whichever retention limit is reached first deletes the oldest files.
`max_total_size` is not a disk cap: active write-ahead logs, catalogs,
and the remote-read cache are additional.

## Partial override example

```yaml
logs:
  retention:
    default:
      max_total_size: "20GB"
      max_age: "30 days"
```

Stock values carry through for any field you omit. Per-tenant entries
(keyed by the `X-Scope-OrgID` value when `auth.enabled: true`) inherit
omitted fields from `default`.

## Offloading to object storage

`remote_storage` is shared by logs and traces. With
`remote_storage.enabled: true`, every sealed file is also uploaded to
`remote_storage.uri` (`s3://` or `fs://`), and queries download offloaded
files into `<base_dir>/remote-read` (bounded by
`remote_storage.read_cache_max_size`, default `1GB`).

```yaml
remote_storage:
  enabled: true
  uri: "s3://my-bucket/netdata-otel?region=us-east-1"
  read_cache_max_size: "4GB"
```

Never put credentials in the URI or in `otel.yaml`. Use the AWS
environment variables, credentials file, or an instance role available
to the `netdata` service. The Agent never deletes offloaded files;
expire them with the object store's lifecycle rules.

## Inspecting ingested logs

Open the node's Logs tab, select the `otel-logs` source, and filter with
the **Services** selector or on a stored field such as
`resource.attributes.service.name`. The view requires a signed-in
Netdata Cloud user of the Agent's Space. `service.namespace` and
`service.name` identify log streams; set them consistently.

The indexed files are not journal files. `journalctl -D` does not read
them.

## Seeing the raw OTLP payload

The former `store_otlp_json` flag no longer exists. To see exactly what a
producer sends, route the same data through an OTel Collector with a
`debug` exporter:

```yaml
exporters:
  debug:
    verbosity: detailed
```

## Trace and span IDs on log records

The log store keeps a record's `trace_id` as a per-record column, not as
a filterable facet (`src/crates/ng-flatten/src/lib.rs` tests in the
Netdata repo). Whether the Logs tab links a log record to its trace in
the Traces tab is not verified; do not promise log-to-trace navigation.
