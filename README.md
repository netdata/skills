# netdata/skills

Agent Skills for setting up, instrumenting, and troubleshooting infrastructure with Netdata.

Status: v0.1.0 under construction. See [CHANGELOG.md](./CHANGELOG.md) for what is shipping.

## What this is

A collection of Anthropic-format Agent Skills, delivered in the open [agentskills.io](https://agentskills.io) layout, that teaches AI coding agents how to:

- Turn on Netdata's OTLP receiver and point services at it.
- Add OpenTelemetry instrumentation to application code that reports to Netdata.
- Configure an OpenTelemetry Collector pipeline with Netdata as an exporter.
- Connect to Netdata via MCP to verify telemetry and query live infrastructure.
- Migrate from Datadog, New Relic, Dynatrace, or Prometheus to Netdata.
- Troubleshoot specific technologies (Postgres, Nginx, Redis, Kafka, etc.) using the Netdata operator playbooks.

## Install

Full per-client install instructions live in [`docs/installation.md`](./docs/installation.md). The short version:

```bash
npx skills add netdata/skills --all
```

## Skills

See [`skills/`](./skills/) for the skill tree. Each skill has a `SKILL.md` (agent-facing), a `README.md` (human-facing), and rule files under `rules/` that the skill references for deeper content.

## Tested end-to-end

The repo ships with a real E2E harness. `bash tests/e2e/run-e2e.sh nodejs` starts a Netdata container, runs a real instrumented Node.js service, generates traffic, and verifies via MCP that Netdata received the metrics.

See [`tests/e2e/README.md`](./tests/e2e/README.md) for the harness layout and how to extend it.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md).

## License

Apache-2.0. See [LICENSE](./LICENSE).
