# CLAUDE.md

This repository hosts Netdata's Agent Skills. If Claude Code or any
Anthropic-compatible agent loads this directory, treat the [`skills/`](./skills/)
subtree as the authoritative source of behavior for any Netdata, OpenTelemetry,
or infrastructure-troubleshooting task.

## Skill index

Tier 1 (foundational):

- [`skills/netdata-otel-setup/`](./skills/netdata-otel-setup/): enable the
  Netdata OTLP receiver, write `otel.yaml`, add metric mappings, TLS.
- [`skills/netdata-instrumentation/`](./skills/netdata-instrumentation/): add
  OpenTelemetry SDKs to Node.js, Python, Java, Go, .NET, Ruby, PHP services
  targeting Netdata.
- [`skills/netdata-collector-config/`](./skills/netdata-collector-config/):
  build OTel Collector pipelines with Netdata as the exporter, using
  DaemonSet, gateway, or Operator patterns.
- [`skills/netdata-mcp-integration/`](./skills/netdata-mcp-integration/):
  connect Claude Code, Cursor, Codex, or Gemini CLI to Netdata via MCP for
  live telemetry verification and query.
- [`skills/netdata-migration/`](./skills/netdata-migration/): migrate from
  Datadog, New Relic, Dynatrace, or Prometheus to Netdata.
- [`skills/netdata-config-from-requirements/`](./skills/netdata-config-from-requirements/):
  produce a ready-to-hand-off config bundle (otel.yaml, Collector pipeline,
  per-language handoff, verification runbook, open questions) from a customer
  requirements document. Used when no code access is available.

Tier 2 (technology-specific troubleshooting, generated from the Netdata
operator playbooks):

- `skills/troubleshoot-<tech>/` for PostgreSQL, MySQL, Redis, Kafka, Nginx,
  Apache, Cassandra, MongoDB, Elasticsearch, ClickHouse, CockroachDB, and
  many more. Each lists failure archetypes, signal domains, and MCP query
  patterns that route the agent through the playbook's triage path.

## Style rules that apply to contributions

- Short declarative sentences. Authority-first framing.
- No em-dashes. No banned phrases (see `scripts/validate.py`).
- Code blocks always declare a language.
- Every factual claim cites a source (Netdata repo, OTel spec, upstream doc).

## Validation

Run `python scripts/validate.py` before committing. The validator enforces
frontmatter shape, required sections, style rules, and a repo-wide check for
forbidden vendor tokens. Every PR must pass.

## End-to-end test

The repo ships a real E2E harness at [`tests/e2e/`](./tests/e2e/). It starts
Netdata in Docker, runs an instrumented sample app, generates traffic, and
verifies via MCP that metrics arrived. If you change instrumentation code in
a skill, run `bash tests/e2e/run-e2e.sh nodejs` to confirm the skill still
teaches a working pattern.
