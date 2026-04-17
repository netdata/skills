# netdata/skills

Agent Skills for setting up, instrumenting, and troubleshooting infrastructure with Netdata.

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Skills format: agentskills.io](https://img.shields.io/badge/format-agentskills.io-informational)](https://agentskills.io/)

## What this is

A collection of Anthropic-format Agent Skills, delivered in the open [agentskills.io](https://agentskills.io) layout, that teaches AI coding agents how to work with Netdata. Skills are portable across Claude Code, Cursor, Windsurf, Codex, Copilot, Cline, Zed, Gemini CLI, and Continue.dev.

Each skill is a pair of files: a `SKILL.md` that the agent loads when a user's request matches the skill's `description`, and a set of `rules/*.md` files the skill references for deeper content. The skill bodies are operator documentation, not marketing copy.

## Install

The repo ships a `.claude-plugin/plugin.json` manifest and a `.claude-plugin/marketplace.json` declaration, so it installs into Claude Code via the plugin marketplace mechanism with no extra glue.

### Claude Code (public install, once the repo is public)

```text
/plugin marketplace add netdata/skills
/plugin install netdata-skills@netdata-skills
```

Restart the session (or `/plugin reload`) and the 54 skills activate automatically when a prompt matches a `description`.

### Claude Code (internal testing, private repo)

If you have access to the private `netdata/skills` repo, clone via SSH and point Claude Code at the local checkout as a marketplace:

```bash
git clone git@github.com:netdata/skills.git ~/netdata-skills
```

```text
/plugin marketplace add ~/netdata-skills
/plugin install netdata-skills@netdata-skills
```

Local paths work identically to GitHub URLs for `/plugin marketplace add`. Pull the repo later to pick up changes; run `/plugin marketplace update netdata-skills` to refresh the index.

### Verify the install worked

Start a fresh Claude Code session and paste:

> Set up Netdata to receive OTLP metrics from my services.

The agent should load `netdata-otel-setup` and walk you through `otel.yaml`. If it does, every other skill is reachable the same way.

For a broader round-trip — real Netdata container, real instrumented app, real MCP probe — run `bash tests/e2e/run-e2e.sh nodejs`; green means the skill teaches a working pattern.

### Other agents

The pack is cross-client: `AGENTS.md` at the repo root covers Cursor, Codex, Gemini CLI, Copilot, Zed, Continue.dev, and OpenCode. Per-client paths are in [`docs/installation.md`](./docs/installation.md).

## Skills

### Tier 1 (foundational)

| Skill | When it fires |
|---|---|
| [`netdata-otel-setup`](./skills/netdata-otel-setup/) | enabling OTLP on Netdata, editing `otel.yaml`, mapping metrics to charts |
| [`netdata-instrumentation`](./skills/netdata-instrumentation/) | adding OpenTelemetry SDKs to Node.js, Python, Java, Go, .NET, Ruby, PHP |
| [`netdata-collector-config`](./skills/netdata-collector-config/) | building OTel Collector pipelines (DaemonSet, gateway, Operator) into Netdata |
| [`netdata-mcp-integration`](./skills/netdata-mcp-integration/) | connecting Claude Code, Cursor, Codex, Gemini CLI to Netdata via MCP |
| [`netdata-migration`](./skills/netdata-migration/) | migrating from Datadog, New Relic, Dynatrace, or Prometheus |

### Tier 2 (troubleshooting, 49 skills)

One skill per technology, generated from the Netdata operator playbooks:

ActiveMQ, Apache HTTPD, Apache Pulsar, BIND DNS, Cassandra, Ceph, ClickHouse, CockroachDB, Consul, CoreDNS, Docker Engine, Elasticsearch, Envoy, Fluentd, HAProxy, Kafka, Kubernetes (API server, cluster state, kube-proxy, kubelet), Logstash, LVM, Memcached, Microsoft SQL Server, MongoDB, MySQL, NATS, nginx, Nvidia DCGM, Nvidia GPU, NVMe, Oracle Database, PgBouncer, PHP-FPM, Postfix, PostgreSQL, ProxySQL, RabbitMQ, Redis, SMART disk, Tomcat, Traefik, uWSGI, Varnish, VMware vCSA/vSphere, ZFS, ZooKeeper.

Each triggers on the matching technology plus common failure archetypes (connection exhaustion, replication lag, memory pressure, etc.), then routes the agent through MCP queries against the signals the playbook identifies.

## How it works

1. Agent loads the repository.
2. User types a prompt.
3. Agent reads each `SKILL.md`'s frontmatter `description` and matches against the prompt.
4. If a skill matches, the agent loads the body and follows the `Step-by-step`, consulting `rules/*.md` as referenced.
5. Where relevant, the agent queries the user's Netdata via MCP to verify state or cross-reference signals.

## Tested end-to-end

The repo ships a real E2E harness. `bash tests/e2e/run-e2e.sh nodejs` starts Netdata in Docker, runs a real instrumented Express app, generates traffic, and verifies via MCP that Netdata received the metrics. Python is covered by `bash tests/e2e/run-e2e.sh python`.

Both were green at v0.1.0 on the build machine. The Node.js `instrument.js` fixture matches the content of [`skills/netdata-instrumentation/rules/nodejs.md`](./skills/netdata-instrumentation/rules/nodejs.md) byte for byte: the skill teaches exactly what the test runs.

See [`tests/e2e/README.md`](./tests/e2e/README.md) for how to reproduce the harness.

## CI usage

`.github/workflows/validate.yml` runs on every PR (static validation, link check).
`.github/workflows/e2e.yml` runs on main-branch pushes and nightly (the full Docker-in-CI E2E).

For a project-level PR review pattern using `claude -p` with this skill pack loaded, see [`docs/ci-recipes.md`](./docs/ci-recipes.md).

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md). In short: the validator gates every PR; fixture changes and rule changes ship together; accuracy first, brevity second, style third.

Issues: use the templates under [`.github/ISSUE_TEMPLATE/`](./.github/ISSUE_TEMPLATE/). Skill corrections (out-of-date fact, wrong command) are the most welcome category.

## License

Apache-2.0. See [LICENSE](./LICENSE).
