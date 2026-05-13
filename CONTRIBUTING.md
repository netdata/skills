# Contributing

Three rules cover 90% of contributions:

1. `python scripts/validate.py` must pass.
2. New factual claims cite a source.
3. Fixture and rule changes ship in the same PR.

## What to contribute

- **Skill corrections**: a fact, version number, command, or file path has changed in Netdata or upstream. Fix the skill and cite the commit, changelog line, or doc that confirms the new behavior.
- **New skills**: propose via a Skill Request issue first ([`.github/ISSUE_TEMPLATE/skill-request.md`](./.github/ISSUE_TEMPLATE/skill-request.md)). Reviewers need to see the agent-facing scenario the skill solves before the content review.
- **Playbook-derived skills**: the Tier 2 skills are generated from the Netdata operator playbooks. If a playbook is updated, re-run `python scripts/generate-troubleshoot-skills.py` and commit the regenerated files.
- **E2E coverage**: add a language to `tests/e2e/sample-apps/` and extend `tests/e2e/run-e2e.sh`. See [`docs/e2e-testing.md`](./docs/e2e-testing.md).
- **Cookbook patterns**: the [`netdata/otelcol-cookbook`](https://github.com/netdata/otelcol-cookbook) is the source of truth for end-to-end Collector recipes. `skills/netdata-collector-config/rules/recipes.md` instructs the agent to fetch the recipe list live; no local index is maintained. When a new cookbook recipe lands upstream, extract its reusable patterns into the modular rule files. See "Cookbook to skills extraction" below.

## Cookbook to skills extraction

The cookbook is the canonical exercised version of each end-to-end Collector config. The skill pack's job is to extract the reusable building blocks so the agent can assemble configurations the cookbook does not cover. When a new cookbook recipe is published:

- A new **receiver type or receiver-side trick** (network listener, RFC variant, port convention, attribute-attachment behavior) goes into `skills/netdata-collector-config/rules/receivers.md`.
- A new **OTTL transform or processor idiom** (error handling mode, attribute promotion, schema evolution, semantic-convention migration, conditional drops) goes into `skills/netdata-collector-config/rules/processors.md`.
- A new **exporter trick or extension** (durable queue via `file_storage`, retry shape, TLS wrinkle, sending-queue tuning) goes into `skills/netdata-collector-config/rules/exporters-to-netdata.md`.
- A new **deployment shape** (sidecar, hybrid DaemonSet plus gateway, host-network requirements) goes into a new or existing `skills/netdata-collector-config/rules/*-deployment.md`.

Every extracted block must cite the recipe it came from with a link to `https://github.com/netdata/otelcol-cookbook/tree/master/<recipe>`. Do not copy the recipe's full `otelcol.yaml` into a rule file; the rule file teaches the pattern, the cookbook holds the exercised configuration.

## Writing a skill

Follow [`docs/skill-authoring-guide.md`](./docs/skill-authoring-guide.md). The short form:

- Frontmatter: `name`, `description`, `version`, `author`, `license`, `tags`. `name` must match the folder name.
- `description` is the trigger. It must start with "Use when..." and list the concrete situations the skill fires on. Keep under 1024 chars (under 300 is better). Bad descriptions are the #1 reason a skill never activates.
- Required H2 sections: `When to use this skill`, `Key facts`, `Step-by-step`, `Common mistakes`, `Verification`, `References`.
- SKILL.md length: 150 to 400 lines. Rule files: 80 to 300.
- No em-dashes. No banned phrases (see `scripts/validate.py`). No emoji in SKILL.md (emoji in README is fine).

## Style

Short declarative sentences. Authority-first: the rule, then the example. No marketing voice. Code blocks always declare a language.

Skills are operator documentation for machines. The reader is an LLM running in a session with a human operator watching the output. Every unnecessary word costs someone tokens.

## Running the checks locally

```bash
# Static validation (run before every commit)
python scripts/validate.py

# Install smoke test
bash scripts/test-install.sh

# Full E2E (requires Docker, Node.js, Python)
bash tests/e2e/run-e2e.sh nodejs
```

## Fixture-rule sync contract

If you change the SDK init code block in `skills/netdata-instrumentation/rules/nodejs.md`, you must also update `tests/e2e/sample-apps/nodejs/instrument.js` in the same PR. Same for Python. The fixture is the authoritative runnable version; the rule is the doc version; they must match byte for byte so the test proves the doc works.

The validator does not yet enforce this automatically. Reviewers do. Expect a "please update the fixture" comment if you miss it.

## Commit messages

Describe the why, not the what. One to two sentences. Reference issues where relevant.

## Code of conduct

See [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md).
