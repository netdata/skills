# AGENTS.md

Generic bridge file for any agent that supports the `AGENTS.md` discovery
convention (OpenAI Codex, Gemini CLI, and a growing list of other clients).

This repository hosts Netdata's Agent Skills. Treat the [`skills/`](./skills/)
subtree as the authoritative instruction set for Netdata, OpenTelemetry, or
infrastructure-troubleshooting tasks.

## Where to look first

- `skills/netdata-otel-setup/SKILL.md`: enabling OTLP ingestion on Netdata.
- `skills/netdata-instrumentation/SKILL.md`: adding OTel SDKs to application
  code.
- `skills/netdata-mcp-integration/SKILL.md`: connecting this agent to Netdata
  via MCP for telemetry verification.
- `skills/netdata-collector-config/SKILL.md`: building OTel Collector
  pipelines into Netdata.
- `skills/netdata-migration/SKILL.md`: migrating from other vendors.
- `skills/troubleshoot-*/SKILL.md`: per-technology troubleshooting.

## Skill loading

Each skill's `SKILL.md` starts with YAML frontmatter:

```yaml
---
name: <kebab-case>
description: <trigger text>
version: 0.1.0
author: Netdata
license: Apache-2.0
tags: [...]
---
```

Match on the `description` field. If the user's request fits, load the
SKILL.md body, follow the `Step-by-step`, and consult `rules/*.md` files
referenced in the `References` section for deeper guidance.

## Do not

- Claim that Netdata accepts OTLP traces yet. It does not (as of v0.1.0 of
  these skills). Route traces to a different backend.
- Claim that `_nd_chart_instance` is a valid OTLP attribute. It does not
  exist in Netdata's source.
- Emit em-dashes in content you write for this repo. Use colons, semicolons,
  commas, or restructure.

## Validation

`python scripts/validate.py` enforces the above. Run it before any commit.
