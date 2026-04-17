# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `tests/e2e/verify-metrics-cloud.py` and a `cloud` mode in
  `run-e2e.sh` that claim the local Agent into a Netdata Cloud
  space and probe visibility via the Cloud MCP endpoint
  (`https://app.netdata.cloud/api/v1/mcp`). Opt-in; requires
  `NETDATA_CLAIM_TOKEN`, `NETDATA_CLAIM_ROOMS`, and
  `NETDATA_CLOUD_API_TOKEN` env vars.
- `tests/eval/run-description-eval.py` as a repeatable runner for
  the skill-description activation eval. `tests/eval/LAST_EVAL_RESULTS.json`
  captures the latest reviewer pass (28/28 correct picks).

### Changed

- `verify-metrics.py` now uses a `list_metrics q-filter` instead of
  a flat substring match, so MCP verification succeeds without the
  previous REST fallback. Passes cleanly against both Node.js (4
  matched contexts) and Python (9 matched contexts) fixtures.
- `scripts/generate-troubleshoot-skills.py` wraps all prose at 100
  columns, extracts archetypes from more header shapes (`###`,
  `####`, with or without a "Characteristic" prefix), accepts
  all-caps domain headers (RabbitMQ-style), uses domain names as a
  symptom-clause fallback when archetypes are absent, and includes
  up to 5 archetypes (from 3) in the description. All 49 Tier 2
  skills regenerated.

### Fixed

- Validator line-length warnings dropped from 941 to 0.
- Boilerplate `X operational issues` descriptions dropped from 32
  skills to 3 (remaining 3 are playbooks whose section shapes do
  not fit any extractable pattern).
- Generated signal names and archetype titles are now sanitized
  before emission so upstream em-dashes do not leak into any
  generated skill.

## [0.1.0] - 2026-04-17

First public release.

### Added

- Five Tier 1 skills with full rule sets:
  - `netdata-otel-setup`: enable the OTLP receiver, write `otel.yaml`, add metric mappings, configure TLS, and troubleshoot ingestion.
  - `netdata-instrumentation`: add OpenTelemetry SDKs for Node.js, Python, Java, Go, .NET, Ruby, and PHP. Metrics and logs targeting Netdata; trace exporters routed elsewhere until Netdata trace support lands.
  - `netdata-collector-config`: build OTel Collector pipelines (DaemonSet, gateway, OpenTelemetry Operator) that export to Netdata.
  - `netdata-mcp-integration`: connect Claude Code, Cursor, Codex, and Gemini CLI to Netdata's MCP server for live telemetry verification.
  - `netdata-migration`: migrate from Datadog, New Relic, Dynatrace, or Prometheus to Netdata.
- 49 Tier 2 troubleshooting skills (`troubleshoot-<tech>`) generated from the Netdata operator playbooks. Each lists failure archetypes, signal domains, and MCP query patterns.
- Static validator `scripts/validate.py` with 12 checks: frontmatter shape, required sections, style rules, banned phrases, code-block languages, link targets, and a repo-wide forbidden-vendor-token sweep.
- Install smoke test `scripts/test-install.sh`.
- End-to-end harness under `tests/e2e/`. Runs Netdata in Docker, starts an instrumented Node.js or Python service, generates traffic, and verifies arrival via MCP (with REST fallback).
- GitHub Actions workflows: `validate.yml` (per-PR), `e2e.yml` (main + nightly), `release.yml` (on tags).
- Client bridge files: `CLAUDE.md`, `AGENTS.md`, `.claude-plugin/plugin.json`.
- Documentation under `docs/`: installation, CI recipes, MCP integration, E2E testing, skill authoring guide.
- Evaluation material under `tests/eval/` with 30+ canonical user prompts.

### Coverage

- Metrics ingestion: covered for Netdata v2.7.0+.
- Logs ingestion: covered for Netdata v2.9.0+.
- Traces: not covered. Netdata does not yet accept trace signals; the `netdata-instrumentation` skill routes trace exporters to an alternative backend. Planned Netdata trace support in Q2 2026 will be added in a future release.
- E2E verified: Node.js sample (required), Python sample (stretch goal, also passed on the build machine).

### Known caveats

- The E2E verifier prefers MCP but falls back to the REST `/api/v2/contexts` endpoint when the MCP response shape does not expose the service name directly. Tracked as a follow-up. (Resolved in Unreleased.)
- Tier 2 skills are template-generated from the operator playbooks. A small number of playbooks lack the standard SECTION 1 signal catalog; those produce an `overview.md` rule file rather than per-domain rules.
- No Netdata Cloud MCP coverage yet in the harness; the skills document the Cloud endpoint but the test only exercises the local Agent MCP. (Resolved in Unreleased.)
