# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0]

Initial release.

### Added

- Five Tier 1 skills covering OTLP setup, instrumentation, Collector config, MCP integration, and migration from other vendors.
- Tier 2 troubleshooting skills generated from the Netdata operator playbooks (one skill per technology).
- End-to-end test harness running real Netdata, a real instrumented Node.js app, and verification via MCP.
- Static validation script covering frontmatter, structure, style rules, and link checks.
- Install flow for Claude Code, Cursor, Codex, and Gemini CLI.

### Coverage

- Metrics ingestion: covered (Netdata v2.7.0+).
- Logs ingestion: covered (Netdata v2.9.0+).
- Traces: not covered; trace ingestion is not yet available in Netdata. The `netdata-instrumentation` skill routes trace-only cases to an external backend until Netdata trace support lands.
- E2E verified: Node.js sample. Python sample ships but is not yet exercised in CI.
