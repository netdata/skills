# Installation

Per-client install guides. Pick the one that matches your agent.

## Claude Code

### Option A: plugin marketplace

```bash
/plugin marketplace add netdata/skills
/plugin install netdata-skills
```

The skills are loaded automatically on Claude Code startup.

### Option B: local clone

```bash
git clone https://github.com/netdata/skills ~/.claude/skills/netdata-skills
```

Claude Code discovers skills under `~/.claude/skills/`.

### Option C: project-local

Clone into the project:

```bash
cd your-project
git clone https://github.com/netdata/skills .claude/skills/netdata-skills
```

## Cursor

Cursor auto-discovers skills from `.cursor/skills/` and `~/.cursor/skills/`.

User-global:

```bash
git clone https://github.com/netdata/skills ~/.cursor/skills/netdata-skills
```

Project-local:

```bash
cd your-project
git clone https://github.com/netdata/skills .cursor/skills/netdata-skills
```

## Codex (OpenAI)

Codex discovers skills via the `AGENTS.md` convention. Either:

- Add a top-level `AGENTS.md` in your project that references this repo's skills directory, or
- Clone into Codex's user skills directory (version-dependent; check `codex --help`).

## Gemini CLI

```bash
git clone https://github.com/netdata/skills ~/.gemini/skills/netdata-skills
```

Gemini CLI reads `~/.gemini/skills/` on start.

## Universal: `npx skills add`

The [skills CLI](https://agentskills.io) is a client-agnostic installer:

```bash
npx skills add netdata/skills --all
# or
npx skills add netdata/skills --skill netdata-otel-setup
```

Installs into whichever directory the local client expects.

## Copilot

```bash
git clone https://github.com/netdata/skills ~/.copilot/skills/netdata-skills
```

Or:

```bash
/plugin install netdata/skills
```

## Zed, Continue.dev, OpenCode

Zed, Continue.dev, and OpenCode discover skills from `~/.agents/skills/`:

```bash
git clone https://github.com/netdata/skills ~/.agents/skills/netdata-skills
```

## Verifying the install

Ask the agent to list its skills and check `netdata-otel-setup` appears. Or paste one of the canonical prompts from [`../tests/eval/prompts.yaml`](../tests/eval/prompts.yaml) and see if the matching skill activates.

## Updating

Pull the repo on whichever clone path your client uses. Most clients reload on next session start; some need an explicit `/plugin reload` or equivalent.
