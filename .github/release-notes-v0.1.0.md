# netdata/skills v0.1.0

First public release of the Netdata Agent Skills.

## What ships

- **5 Tier 1 skills** covering the foundational operator tasks: enabling Netdata's OTLP receiver, instrumenting application code with OpenTelemetry SDKs, configuring an OTel Collector pipeline to Netdata, connecting AI coding agents to Netdata via MCP, and migrating from Datadog, New Relic, Dynatrace, or Prometheus.
- **49 Tier 2 troubleshooting skills** generated from the Netdata operator playbooks. One per technology, from ActiveMQ through ZooKeeper.
- **Real end-to-end test harness** under `tests/e2e/`. Node.js and Python sample apps instrument themselves with OpenTelemetry, push traffic through a real Netdata container, and verify via MCP (with REST fallback) that the metrics arrived. Both passed green on the release build.

## Verified end-to-end

The Node.js sample app's SDK init code is byte-for-byte identical to `skills/netdata-instrumentation/rules/nodejs.md`. The Python sample app is similarly identical to `rules/python.md`. The test is the documentation; the documentation is what runs.

## Coverage

| Signal | Status |
|---|---|
| Metrics (OTLP/gRPC) | Covered. Netdata v2.7.0+. |
| Logs (OTLP/gRPC) | Covered. Netdata v2.9.0+. |
| Traces | Not covered. Netdata does not yet accept trace signals. Skills route trace exporters to alternative backends until Q2 2026. |

## Install

```bash
# Claude Code
/plugin marketplace add netdata/skills
/plugin install netdata-skills

# Cursor, Gemini CLI, etc.
git clone https://github.com/netdata/skills ~/.cursor/skills/netdata-skills
# or
npx skills add netdata/skills --all
```

Full per-client guide in `docs/installation.md`.

## Caveats

- The E2E verifier prefers MCP but falls back to Netdata's REST API (`/api/v2/contexts`) when the MCP response does not include the service name in the expected shape. Tracked as a v0.2 follow-up.
- Tier 2 skills for playbooks without the standard SECTION 1 signal catalog produce a single `overview.md` rule file rather than per-domain rules.
- No Netdata Cloud MCP coverage in the E2E yet; the skills document the Cloud endpoint and local-Agent MCP is exercised.

## Thanks

This release is the first to ship in the public `netdata/skills` repo. Contributions welcome via the issue templates under `.github/ISSUE_TEMPLATE/`.
