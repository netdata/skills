# Tests

The repo carries four kinds of checks. Each runs independently.

## 1. Static validation

```bash
python scripts/validate.py
```

Enforces frontmatter shape, required H2 sections, style rules (no
em-dashes, no banned phrases, no emoji in SKILL.md), and a repo-wide
sweep for forbidden vendor tokens. Must exit 0 on every PR.

See [`../scripts/validate.py`](../scripts/validate.py) for the full
12-check list.

## 2. Install smoke test

```bash
bash scripts/test-install.sh
```

Copies the repo to a scratch dir, asserts the install payload shape
(package.json, LICENSE, CLAUDE.md, AGENTS.md, five Tier 1 skills with
rules, at least ten Tier 2 skills), and runs the validator inside the
copy. Must exit 0.

## 3. End-to-end test

```bash
bash tests/e2e/run-e2e.sh nodejs
bash tests/e2e/run-e2e.sh python
```

Starts Netdata in Docker, runs a real instrumented sample app, pushes
traffic, and verifies the metrics arrived via MCP (falling back to
REST). The SDK init code in the sample app is byte-for-byte identical
to the matching rule file under
`skills/netdata-instrumentation/rules/`. See
[`e2e/README.md`](./e2e/README.md) for layout, port overrides, and
troubleshooting.

This is the real gate that v0.1.0 ships behind.

## 4. Manual skill-activation test

The validator proves the skills are well-formed. It does not prove
the `description` field triggers the skill when a user types a
natural-language prompt. That needs a human or a second LLM in the
loop.

File: [`eval/prompts.yaml`](./eval/prompts.yaml).

### Protocol (manual)

1. Pick a prompt from `eval/prompts.yaml`.
2. In a clean agent session (Claude Code, Cursor, Codex, or Gemini
   CLI) that has this repo's skills loaded and no other skill
   packages active, paste the prompt.
3. Observe which skill (if any) the agent loaded. Compare to the
   `expected_skill` field.
4. If the skill matched, confirm that the agent then referenced the
   `expected_rule` file. If the skill did not match, record the
   prompt as a trigger miss.

A batch of 10 prompts takes about 20 minutes per client.

### Protocol (semi-automated)

Run

```bash
python tests/eval/run-description-eval.py
```

to dump the current skill index and prompt list to a tempdir and
print a paste-ready prompt. Paste that prompt into a fresh Claude
Code, Cursor, Codex, or Gemini CLI session and collect the JSON
match report. Copy the resulting file to
[`eval/LAST_EVAL_RESULTS.json`](./eval/LAST_EVAL_RESULTS.json) for
the record.

The last-recorded run is checked in; diff against it after any
description edits to catch regressions.

### What to do on a trigger miss

If the right skill exists but the agent did not pick it:

1. Read the prompt and the current skill's `description` field.
2. Add the prompt's distinguishing phrase (or a paraphrase) to
   the description. Keep it under 1024 chars.
3. Re-run the validator.
4. Re-test the prompt.

If the right skill does not exist yet, that is a skill-request
issue, not a trigger fix.

## Adding new test cases

- **Unit-style** (format, link, style): extend
  [`../scripts/validate.py`](../scripts/validate.py).
- **Install payload**: extend
  [`../scripts/test-install.sh`](../scripts/test-install.sh) with a
  new `assert` call.
- **E2E**: add a new sample app under
  [`e2e/sample-apps/<lang>/`](./e2e/sample-apps/) and extend
  [`e2e/run-e2e.sh`](./e2e/run-e2e.sh).
- **Trigger eval**: add prompts to
  [`eval/prompts.yaml`](./eval/prompts.yaml). For new trigger
  keywords, update
  [`eval/expected-triggers.yaml`](./eval/expected-triggers.yaml).

## Current coverage

- Static validation: all 54 skills (5 Tier 1 + 49 Tier 2).
- Install smoke test: top-level layout + Tier 1 + Tier 2 count.
- E2E: Node.js and Python sample apps against a real Netdata
  container.
- Manual skill-activation: 30+ prompts in `eval/prompts.yaml`.
