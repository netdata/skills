# OTel logs instrumentation: Python reference implementation

**Status:** design, pending implementation plan
**Date:** 2026-04-20
**Owner:** Netdata skills team
**Related skills:** `skills/netdata-instrumentation/`, `skills/netdata-otel-setup/`
**Related tests:** `tests/e2e/`

## Problem

Netdata's stable agent accepts OTLP logs over gRPC. The `netdata-otel-setup` skill documents the ingestion path (`skills/netdata-otel-setup/rules/log-ingestion.md`). However:

1. Every rule in `skills/netdata-instrumentation/rules/` currently sets `OTEL_LOGS_EXPORTER=none`, actively telling users not to send logs via OTLP.
2. No sample app in `tests/e2e/sample-apps/` emits logs.
3. The E2E harness verifies metrics ingestion only. No assertion ever runs against the logs path.

Net effect: users following the `netdata-instrumentation` skill will not send logs to Netdata even though Netdata accepts them. The skill teaches a narrower pattern than Netdata supports.

## Goal

Ship a verified end-to-end OTel logs path for one reference language (Python) in a single PR. Use the proven pattern to roll out the remaining languages in follow-up PRs. Keep the fixture-rule byte-for-byte sync contract intact.

## Non-goals

* Not updating the other six language rules in this PR. Each stays at its current stance, with a one-line header pointing to the Python reference once it lands.
* Not adding a new language fixture (for example, Java). Python fixture already exists; extending it is the smallest change that exercises the full path.
* Not reshaping the MCP query-patterns skill. Verification uses `journalctl -D` inside the Netdata container, which is the canonical inspection method per `netdata-otel-setup/rules/log-ingestion.md`.
* Not altering the harness `otel.yaml`. OTLP log ingestion is always on once `otel-plugin` runs; stock defaults apply.

## Architecture

```text
sample-apps/python/app.py           (emits one structured log per /hello)
  -> Python stdlib logging
instrument.py                        (LoggerProvider + LoggingHandler)
  -> OTLPLogExporter over gRPC
Netdata OTLP receiver (:4317)
  -> always-on log ingestion path
/var/log/netdata/otel/v1/*.journal   (systemd-compatible journal files)
  ^ journalctl -D /var/log/netdata/otel/v1 SERVICE_NAME=hello-python
verify-metrics.py --signal logs      (greps a distinctive log line)
```

No new process. No Collector sidecar. No harness config change on the Netdata side.

## Components

### 1. `skills/netdata-instrumentation/rules/python.md`

**"Minimal SDK init" fenced block** (the one the fixture mirrors byte-for-byte) extends the current metrics wiring with a logs pipeline:

* `LoggerProvider` built from the same `Resource` used by `MeterProvider`.
* `BatchLogRecordProcessor` wrapping `OTLPLogExporter` (gRPC).
* `LoggingHandler` attached to the root logger at `INFO`.

The block stays a single fenced code region so the fixture sync contract remains one-file-to-one-block.

**"Auto-instrumentation via opentelemetry-instrument" block** flips:

* `--logs_exporter none` to `--logs_exporter otlp`.
* Prose note explaining that `opentelemetry-instrument` auto-wires the stdlib `logging` module when `--logs_exporter otlp` is set; no code change needed in `app.py` on that path.

**"Required environment variables" block** flips:

* `OTEL_LOGS_EXPORTER=none` to `OTEL_LOGS_EXPORTER=otlp`.

**"Traces" section** unchanged. Netdata still does not accept traces.

**New "What Netdata does with OTLP logs" subsection** (one short paragraph):

* Cross-links `skills/netdata-otel-setup/rules/log-ingestion.md` so the user knows where logs land on disk, how rotation works, and how to inspect with `journalctl -D`.
* Cites the ingestion guarantee (always on once `otel-plugin` runs).

### 2. `tests/e2e/sample-apps/python/instrument.py`

Byte-for-byte copy of the updated `python.md` "Minimal SDK init" fenced block.

### 3. `tests/e2e/sample-apps/python/app.py`

Adds:

* `import logging` and `logger = logging.getLogger("hello-python")` at module top, after `import instrument`.
* Inside the `/hello` handler: `logger.info("hello-python request served", extra={"route": "/hello"})`.

The log message string `"hello-python request served"` is the verification anchor. It must be stable; a change to it is a coordinated change with the verifier.

### 4. `tests/e2e/sample-apps/python/requirements.txt`

Audit at implementation time. The existing `opentelemetry-exporter-otlp-proto-grpc` package ships both the metric and log exporter modules, and `opentelemetry-sdk` covers `_logs`. Expected new entries: zero. If the audit shows an additional pin is needed, add the minimum required package.

### 5. `tests/e2e/verify-metrics.py`

* New `--signal {metrics,logs,both}` flag, default `both`.
* New `try_journalctl_verification(service_name, anchor_substring)` function.
  * Invokes `docker exec netdata-skills-e2e journalctl -D /var/log/netdata/otel/v1 SERVICE_NAME=<svc> --since "5 minutes ago" --no-pager -o cat`.
  * Returns (True, message) on a non-empty match for `anchor_substring`.
  * Returns (False, message) with stderr context on failure.
* `verify_with_retries` gains a signal parameter and calls the journalctl check on each attempt when `signal` includes `logs`.
* CLI help text updated.

File name stays `verify-metrics.py` for this PR. A future rename to `verify-signals.py` is a separate, trivial follow-up once logs verification is present for more than one language.

### 6. `tests/e2e/run-e2e.sh`

* Python path: `python3 verify-metrics.py --app python --signal both`.
* Node.js path: `python3 verify-metrics.py --app nodejs --signal metrics` (unchanged behavior, explicit flag).
* Exit code semantics unchanged: any failed signal fails the run.

### 7. Non-Python language rules (touched only to prevent drift)

Each of `dotnet.md`, `go.md`, `java.md`, `nodejs.md`, `php.md`, `ruby.md` gains a single admonition block near the top of its "Logs" section:

> The current Python rule ships a verified OTLP logs reference (`python.md`). Equivalent guidance for this language is tracked as a follow-up. Until it lands, the logs guidance in this file has not been re-verified against Netdata's stable OTLP log ingestion path.

No code changes, no env-var flips in these six files. Separate PRs flip them one at a time as each language's logs path is verified in the harness.

### 8. Memory update

`feedback_fixture_rule_sync.md` updated to reflect that the Python fixture mirrors the combined metrics-plus-logs fenced block. Contract wording unchanged: same-PR edits, byte-for-byte diff check, fixture is source of truth.

### 9. Changelog

`CHANGELOG.md` gains an entry under the next version describing the new Python logs reference and the harness signal flag.

## Data flow, timing, and retry budget

* Python fixture starts; `instrument.py` spins up both exporters; traffic generator runs; each `/hello` request emits one log record.
* `BatchLogRecordProcessor` flushes on its default interval. The existing metrics reader runs at 5 s; the log batch processor default is 1 s scheduled delay with a 5 s export timeout.
* Netdata writes log records to the journal directory as they arrive.
* Verifier uses the same retry loop as metrics: six attempts, five seconds apart, max 30 seconds. That covers both the batch flush and the journal write.

## Error handling

* `journalctl` returns non-zero when the journal directory is empty. The verifier treats that as "not yet, retry" on intermediate attempts and as a failure on the final attempt.
* `docker exec` failure (container gone, name mismatch) is surfaced verbatim in the failure message so the run script log names the actual cause.
* Export failures from the Python SDK log to stderr by default. The sample app does not silence them; E2E stderr stays visible via `docker logs` on failure.

## Testing strategy

* Primary: the E2E harness. Green run on `bash tests/e2e/run-e2e.sh python` is the acceptance signal. Exit code 0 means both metrics and logs verified.
* Secondary: a byte-diff assertion in the validator between the `python.md` minimal-init fenced block and `instrument.py`. The contract is currently documented in memory and enforced by hand; this PR lifts it into `scripts/validate.py` so CI fails fast on drift. The check is generic and ready to cover the nodejs fixture-rule pair in the same pass.
* Tertiary: validator pass (`python scripts/validate.py`) covering style rules, banned phrases, and link integrity for the new cross-reference into `log-ingestion.md`.

## Open questions

None load-bearing. Two small implementation-time checks:

1. Confirm `opentelemetry-sdk._logs` is importable on the pinned SDK version in `requirements.txt`. Upstream marked it stable in a recent release; confirm on the version actually installed.
2. Confirm `SERVICE_NAME` is the correct journal field name emitted by Netdata's flattener for the OTel `service.name` resource attribute. `log-ingestion.md` documents the uppercase convention; confirm with a direct `journalctl` probe during implementation.

## Out of scope, deferred to follow-up PRs

* Java javaagent logs wire-up. Priority one follow-up, matches the user's current live test target (spring-petclinic).
* Node.js logs SDK wire-up. Priority two, the SDK is the least mature of the three.
* .NET, Go, Ruby, PHP logs wire-up. Sequenced after Node.js.
* A Java sample app in the harness. Needed before Java can be verified end-to-end the same way Python is in this PR.
