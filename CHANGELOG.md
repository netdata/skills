# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

- The E2E verifier prefers MCP but falls back to the REST `/api/v2/contexts` endpoint when the MCP response shape does not expose the service name directly. Tracked as a follow-up.
- Tier 2 skills are template-generated from the operator playbooks. A small number of playbooks lack the standard SECTION 1 signal catalog; those produce an `overview.md` rule file rather than per-domain rules.
- No Netdata Cloud MCP coverage yet in the harness; the skills document the Cloud endpoint but the test only exercises the local Agent MCP.
