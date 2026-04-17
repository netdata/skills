# Skill authoring guide

How to write a SKILL.md that triggers reliably and carries content the agent can use.

## Anatomy

```markdown
---
name: kebab-case-name
description: Use when <situation X>, <situation Y>, or <situation Z>. Covers <scope>.
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - <other>
---

# <Skill title>

## When to use this skill
<bulleted trigger list, mirrors description but expanded>

## Key facts
<5 to 10 bullets. Version numbers, what is supported, what is not.>

## Step-by-step
<numbered steps. Each step has a code block where relevant.>

## Common mistakes
<bulleted list of anti-patterns and the correct form>

## Verification
<how to confirm the setup worked. Include a specific command or MCP query.>

## References
<links to rules/*.md files + upstream docs>
```

## `description` is the trigger

The agent reads every skill's frontmatter, compares the user prompt against the `description`, and decides which skill to load. A weak description means the skill never fires.

### Good description

```yaml
description: Use when enabling the Netdata otel.plugin, writing /etc/netdata/otel.yaml, defining metric-to-chart mappings, configuring TLS on the OTLP receiver, or debugging OTLP ingestion issues with Netdata. Covers OTLP gRPC ingestion for metrics (v2.7.0+) and logs (v2.9.0+). Traces are not yet supported.
```

Why it works:

- Starts with "Use when".
- Lists three specific tasks a user might ask about.
- Mentions concrete identifiers (`otel.plugin`, `/etc/netdata/otel.yaml`, `OTLP gRPC`) the agent can match on.
- States a scope boundary (traces not yet supported).

### Bad description

```yaml
description: Netdata OpenTelemetry configuration.
```

Why it fails:

- Too short.
- No trigger words a user would actually type.
- No scope.
- No "Use when".

## Writing the body

- **Short declarative sentences.** "Netdata accepts OTLP gRPC on port 4317." Not "You might want to consider that Netdata's support for OpenTelemetry includes the OTLP gRPC protocol on port 4317."
- **Authority-first.** State the fact, then the reasoning only if needed. If the reasoning is not needed, drop it.
- **Every code block declares a language.** ```` ```yaml ```` not ```` ``` ````. The validator enforces this.
- **Every file path in prose is backticked.** `/etc/netdata/otel.yaml`, not /etc/netdata/otel.yaml.
- **Cite sources for version-specific claims.** Not with URLs (which rot) but by naming the file in the Netdata repo or the section of the upstream spec. Example: "see `src/crates/netdata-otel/otel-plugin/src/plugin_config/env.rs` for the env-var list."

## Style bans

Hard bans (validator-enforced):

- No em-dashes (`—` or `--` outside code blocks). Use colons, semicolons, commas, or restructure.
- No banned phrases: "genuinely", "I'd love to", "dive in", "delve into", "leverage", "game-changing", "seamlessly", "robust", "powerful", "cutting-edge".
- No emoji in SKILL.md (README.md emoji is fine).
- No vendor references outside of the ones the skill is explicitly about. No comparisons between Netdata and specific competitors by name.

Soft bans (reviewer-enforced):

- No tricolons with diverse-geography signalling ("from Tokyo to Toronto").
- No performed profundity.
- No mechanical problem-agitation-solution structure.
- No marketing voice. Skills are operator docs for machines.

## Rule files

Rule files under `rules/` hold deeper content that a skill's body references. Typical structure:

```markdown
# Rule title

## Scope

<one paragraph: what this rule covers, when to consult it>

## <Topic 1>

<content>

## <Topic 2>

<content>
```

Rule files do not need frontmatter. They do need to be under 300 lines. A rule that wants to grow past 300 lines should split.

## Testing your skill

1. Run `python scripts/validate.py` locally. Fix every error.
2. Add a trigger prompt to `tests/eval/prompts.yaml`.
3. In a clean agent session, paste the prompt. Confirm your new skill activates.
4. Ask the agent to perform the task the skill teaches. Watch for any step where the agent goes off-script or invents a fact the skill did not provide.
5. If it invents a fact, add that fact to the skill explicitly.

## Sizing

- SKILL.md: 150 to 400 lines.
- Rule files: 80 to 300 lines.
- Frontmatter description: under 1024 chars, under 300 if possible.

Going under means the skill is thin. Going over means the skill is doing too much; split.

## Fact accuracy

The #1 failure mode for a skill is to confidently state something that is no longer true. Before you ship a version-specific claim:

1. Find the source in the Netdata repo, OTel spec, or upstream SDK.
2. Paste the citation into the PR description (file + line is ideal).
3. If the source contradicts your recollection, trust the source.

A skill is high-leverage: one claim, many users who act on it. A small error compounds.
