# Log ingestion

## Scope

OTLP/gRPC log ingestion is always on once `otel-plugin` is running. This
rule covers journal storage, rotation policy, inspection, and a debug flag
for capturing the full OTLP envelope.

## Storage

Ingested log records are written to systemd-compatible journal files. The
default directory is:

```text
/var/log/netdata/otel/v1
```

Override with `logs.journal_dir` in `otel.yaml` only when the default path
is not writable by the `netdata` user.

## Rotation policy

All knobs are settable in `otel.yaml` under `logs:`. Defaults:

| Field | Default | What it controls |
|---|---|---|
| `size_of_journal_file` | `100MB` | Size cap before rotating to a new file. |
| `entries_of_journal_file` | `50000` | Entry count cap before rotating. |
| `duration_of_journal_file` | `2 hours` | Time span cap per file. |
| `number_of_journal_files` | `10` | Maximum files retained. |
| `size_of_journal_files` | `1GB` | Total size cap across all files. |
| `duration_of_journal_files` | `7 days` | Maximum age across all files. |
| `store_otlp_json` | `false` | Also store the raw OTLP JSON per record. |

Whichever cap is reached first triggers rotation. Whichever retention cap
is reached first triggers deletion.

## Partial override example

```yaml
logs:
  number_of_journal_files: 20
  duration_of_journal_files: "14 days"
```

Stock values carry through for any field you omit.

## Inspecting ingested logs

Use `journalctl` with the `-D` flag pointing at the journal dir:

```bash
sudo journalctl -D /var/log/netdata/otel/v1 -f
```

Filter by resource attribute. OpenTelemetry resource attributes are
exposed as journal fields with upper-case names:

```bash
sudo journalctl -D /var/log/netdata/otel/v1 \
  SERVICE_NAME=checkout \
  --since "5 minutes ago"
```

The Netdata dashboard's Logs tab reads from the same directory.

## Debugging with `store_otlp_json`

Set to `true` when you need to inspect the exact OTLP payload a producer
sent, including attributes the mapper dropped.

```yaml
logs:
  store_otlp_json: true
```

Each journal entry then carries the full OTLP log record as a JSON blob in
a dedicated field. Disk usage increases substantially; turn it off once
debugging is finished.

## What trace-id and span-id look like

If the OTLP log record carries `trace_id` or `span_id`, those fields are
currently not surfaced as first-class journal fields. The flattener has
commented-out code for this. Do not build a skill-fed workflow that
depends on trace/span correlation in logs until a release adds it.
