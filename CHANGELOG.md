# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `netdata-collector-config` now references the
  [`netdata/otelcol-cookbook`](https://github.com/netdata/otelcol-cookbook)
  repo as the source of truth for end-to-end Collector recipes.
  `rules/recipes.md` instructs the agent to fetch the cookbook recipe
  list live (no static local index) and documents the conventions
  every recipe follows. The cookbook's first recipe (`syslog-ingest`)
  prompted additions to:
  - `rules/receivers.md`: a `syslog` receiver section covering UDP /
    TCP listeners, RFC 3164 vs RFC 5424, the `location` (timezone)
    field, and the non-privileged-port convention the cookbook uses.
  - `rules/processors.md`: `error_mode: ignore` guidance for OTTL
    transforms, the log-attribute to resource-attribute promotion
    pattern, and the schema-evolution block that rewrites legacy
    `net.*` attributes to current OTel semantic conventions
    (`client.address`, `server.port`, `network.transport`).
  - `rules/exporters-to-netdata.md`: a `file_storage` extension recipe
    for durable exporter sending queues that survive Collector
    restarts.
- Cookbook / skills feedback loop documented in both directions.
  `CONTRIBUTING.md` gains a "Cookbook to skills extraction" section
  listing where each kind of cookbook pattern (receiver, processor,
  exporter, deployment) folds into the modular rule files.
  `rules/recipes.md` gains a "When to suggest a new cookbook recipe"
  section so the agent tells the user to upstream non-trivial,
  reusable compositions it assembled from the modular rules.
- `tests/e2e/verify-metrics-cloud.py` and a `cloud` mode in
  `run-e2e.sh` that claim the local Agent into a Netdata Cloud
  space and probe visibility via the Cloud MCP endpoint
  (`https://app.netdata.cloud/api/v1/mcp`). Opt-in; requires
  `NETDATA_CLAIM_TOKEN`, `NETDATA_CLAIM_ROOMS`, and
  `NETDATA_CLOUD_API_TOKEN` env vars.
- `tests/eval/run-description-eval.py` as a repeatable runner for
  the skill-description activation eval. `tests/eval/LAST_EVAL_RESULTS.json`
  captures the latest reviewer pass (28/28 correct picks).
- Validator now checks every `rules/*.md` file (288 at the time of
  writing), not just `SKILL.md`, for style, structure, and code-block
  shape. Closes the gap where rule files could ship with em-dashes,
  missing code-block languages, or banned phrases and still pass.
- Validator enforces Tier 2 context reality. Every `troubleshoot-<tech>`
  skill with a known Netdata collector mapping must name at least
  three real contexts from that collector's `metadata.yaml` (or every
  context the collector emits, for small collectors like LVM and
  Postfix). Any backtick-wrapped `<prefix>.<name>` reference under the
  mapped prefix that does not exist in `metadata.yaml` is flagged as
  potentially fabricated.
- Python E2E job in `.github/workflows/e2e.yml` alongside the Node.js
  job. Prior to this, the README claimed Python coverage but only
  Node.js was actually exercised on every push.

### Changed

- `scripts/generate-troubleshoot-skills.py` now reads each tech's
  Netdata collector `metadata.yaml` (via a `PLAYBOOK_TO_COLLECTOR`
  mapping) and emits concrete context names in every generated
  `SKILL.md` verification block and in each domain's rule file.
  Contexts are bucketed into playbook domains by keyword overlap over
  name, description, and dimension fields. Unbucketed contexts go
  into a generated `other-contexts.md` rule file so nothing is lost.
  Techs without a native collector (Kafka) fall back to honest
  discovery-style guidance.
- `netdata-mcp-integration/SKILL.md` reconciles with the code that
  actually ships: Cloud MCP is described as a production endpoint at
  `https://app.netdata.cloud/api/v1/mcp` (Streamable HTTP, bearer
  token) rather than pre-GA; local Agent transports are version-gated
  correctly (WebSocket v2.6.0+, HTTP streamable and SSE v2.7.2+).
- `netdata-mcp-integration/rules/connect-codex.md` rewritten to the
  current Codex config schema (`~/.codex/config.toml`,
  `[mcp_servers.<name>]` tables, `bearer_token_env_var` for HTTP
  servers) per developers.openai.com/codex/mcp. Includes both HTTP
  and stdio forms and cites the version gate for each.
- `verify-metrics.py` now uses a `list_metrics q-filter` instead of
  a flat substring match, so MCP verification succeeds without the
  previous REST fallback. Passes cleanly against both Node.js (4
  matched contexts) and Python (9 matched contexts) fixtures.
- `scripts/generate-troubleshoot-skills.py` wraps all prose at 100
  columns, extracts archetypes from more header shapes (`###`,
  `####`, with or without a "Characteristic" prefix), accepts
  all-caps domain headers (RabbitMQ-style), uses domain names as a
  symptom-clause fallback when archetypes are absent, and includes
  up to 5 archetypes (from 3) in the description.
- Generator sanitizer additionally swaps style-banned words (powerful,
  robust, leverage, seamlessly, etc.) for neutral equivalents so
  playbook prose cannot smuggle banned phrases into generated skills.
- `AGENTS.md` and `docs/ci-recipes.md` clarify that `_nd_dimension`
  exists only inside Netdata's OTel consumer (histogram flattening)
  and is not a producer-side attribute; `_nd_chart_instance` does not
  exist at all.

### Fixed

- Tier 2 skills now name the real Netdata contexts the agent should
  query. Previously the verification block said "list_metrics filtered
  by the <tech> service's context prefix" without naming the prefix;
  generated rule files did the same. Redis, for example, now cites
  `redis.connections`, `redis.clients`, `redis.ping_latency`,
  `redis.keyspace_lookup_hit_rate`, `redis.mem_fragmentation_ratio`,
  and the rest of the 25 contexts its collector emits.
- Hand-written Tier 1 rule files under `netdata-collector-config/`
  and `netdata-otel-setup/` had untagged ASCII-art code blocks and a
  handful of em-dashes that slipped past the previous SKILL-only
  validator. Both are now clean.
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
