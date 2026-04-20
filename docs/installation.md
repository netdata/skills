# Installation

Per-client install guides. Pick the one that matches your agent.

## Claude Code

### Option A: plugin marketplace (public repo)

```text
/plugin marketplace add netdata/skills
/plugin install netdata-skills@netdata-skills
```

### Option B: plugin marketplace (local checkout, for internal testing)

```bash
git clone git@github.com:netdata/skills.git ~/netdata-skills
```

```text
/plugin marketplace add ~/netdata-skills
/plugin install netdata-skills@netdata-skills
```

`/plugin marketplace add` accepts both GitHub slugs and absolute local paths, so the same install flow works against a private checkout.

### Option C: direct skill drop (no plugin system)

Skip the plugin mechanism entirely and drop the skills into Claude Code's global skills directory:

```bash
git clone git@github.com:netdata/skills.git ~/src/netdata-skills
ln -s ~/src/netdata-skills/skills/* ~/.claude/skills/
```

Claude Code picks up every `SKILL.md` under `~/.claude/skills/` on session start. Use project-level `.claude/skills/` (shared) or `.claude/skills.local/` (gitignored) for per-project scoping.

## Cursor, Codex, Gemini CLI, and other AGENTS.md-aware agents

Most non-Claude-Code agents read an `AGENTS.md` bridge file rather than loading skill frontmatter directly. The repo ships an `AGENTS.md` at the root that points at the skills directory.

The portable install is a clone plus a project-level symlink or include:

```bash
git clone git@github.com:netdata/skills.git ~/src/netdata-skills
```

Then either:

1. In your project's own `AGENTS.md`, add a line that sources the skills directory, e.g. `@~/src/netdata-skills/AGENTS.md`; or
2. Symlink the skills subtree into whatever convention your client documents (paths differ; check your client's docs).

We are tracking client-specific install paths as they stabilize. If your client supports the Agent Skills format directly, the relevant content is at `<checkout>/skills/<skill-name>/SKILL.md`.

## Verifying the install

Ask the agent to list its skills and confirm `netdata-otel-setup` appears, or paste one of the canonical prompts from [`../tests/eval/prompts.yaml`](../tests/eval/prompts.yaml) and check the expected skill activates.

For a deeper round-trip test, run the end-to-end harness:

```bash
bash tests/e2e/run-e2e.sh nodejs
```

Green means Netdata receives real OTLP traffic from a sample app that was instrumented per the skill's rule file.

## Updating

Pull the repo on whichever clone path your client uses. Claude Code: `/plugin marketplace update netdata-skills`. Other clients: restart the session after `git pull`.
