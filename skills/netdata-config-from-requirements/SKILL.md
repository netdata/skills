---
name: netdata-config-from-requirements
description: "Use when a customer or prospect has sent a written requirements document, architecture brief, or RFP and the deliverable is a config bundle (Netdata otel.yaml, OpenTelemetry Collector pipelines, per-language instrumentation handoff, verification playbook) that the customer applies themselves. Unlike netdata-instrumentation and netdata-otel-setup, this skill operates without access to the customer's codebase or running infrastructure: inputs are prose, outputs are YAML files, Markdown runbooks, and an explicit list of open questions for the account team. Covers requirements extraction, ambiguity flagging, bundle layout, and composition with netdata-otel-setup, netdata-collector-config, netdata-instrumentation, and netdata-migration."
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - opentelemetry
  - otel
  - requirements
  - consulting
  - pre-sales
  - config-generation
---

# Netdata config from requirements

This skill turns a written requirements document into a ready-to-hand-off
config bundle. The target user is a Netdata SE, solutions architect, or
partner engineer who receives a customer brief and must produce YAML
artifacts and a runbook the customer applies on their own systems.

The other Tier 1 skills assume access to the target system. This one does
not. The loop is: read prose, extract atomic requirements, compose the
bundle by delegating to the sibling skills, flag every ambiguity back to
the account team.

## When to use this skill

- A customer or prospect sends a requirements doc, RFP, technical brief,
  or architecture diagram and expects Netdata-ready configs in return.
- Pre-sales or solution engineering work where the agent must produce
  `otel.yaml`, Collector pipelines, and per-language instrumentation
  guidance without touching the customer's codebase.
- Converting a migration spec (for example "we are leaving Datadog by
  Q3") into a phased config plan.
- Any request that includes phrases like "draft the config for us,"
  "what would this look like for our stack," or "generate the YAML so
  our platform team can review it before we install."

Do not use this skill when the user has shell access, a git checkout,
or a running Netdata to query. In those cases the sibling skills
(`netdata-otel-setup`, `netdata-collector-config`,
`netdata-instrumentation`, `netdata-mcp-integration`) are sharper: they
can verify their own output against live state. This skill deliberately
trades that verification for portability.

## Key facts

- **Input is prose.** The requirements document is the only source of
  truth. Do not invent values the document did not state. Flag every
  gap as an open question instead.
- **Output is a bundle.** Not a chat response. Always produce a folder
  tree with YAML files, Markdown runbooks, and an open-questions
  manifest. See [`rules/deliverable-bundle.md`](./rules/deliverable-bundle.md).
- **Delegate, do not duplicate.** The receiver-side config is owned by
  [`netdata-otel-setup`](../netdata-otel-setup/). The Collector-side is
  owned by [`netdata-collector-config`](../netdata-collector-config/).
  The instrumentation handoff is shaped by
  [`netdata-instrumentation`](../netdata-instrumentation/). Migrations
  use [`netdata-migration`](../netdata-migration/). This skill is a
  composition layer; it references the sibling rules, it does not
  paraphrase them. See [`rules/composing-skills.md`](./rules/composing-skills.md).
- **Ambiguities are first-class.** A requirements doc that fails to
  specify TLS posture, volume estimates, or the target deployment
  topology is the normal case, not the exception. Every missing value
  becomes an entry in `open-questions.md` in the bundle, so the account
  team can resolve it with the customer before the configs land on a
  production system.
- **Verification is the customer's job.** The bundle includes a
  `verify.md` that the customer runs after applying the configs.
  `netdata-mcp-integration` is out of scope here; it presumes a live
  Netdata this skill cannot reach.

## Step-by-step

1. **Read the requirements document end to end** before writing
   anything. If the user pasted prose inline, read the whole paste
   first. If they attached a file, read the file. Do not partial-parse.
2. **Extract the requirement inventory.** Follow
   [`rules/extract-requirements.md`](./rules/extract-requirements.md).
   The output is a structured list with categories for stack inventory,
   volume estimates, network topology, security posture, compliance
   constraints, deployment pattern, and acceptance criteria.
3. **Flag every ambiguity and missing value.** Anything the document
   does not specify becomes an open question. Do not guess a default
   silently. `rules/extract-requirements.md` contains the specific
   categories where missing values most often hide.
4. **Decide which sibling skills to compose.** The requirements
   determine which:
   - Always: `netdata-otel-setup` (every bundle ships an `otel.yaml`
     snippet, even a minimal one, so the Netdata side is explicit).
   - If the customer will run a Collector: `netdata-collector-config`.
   - If the customer will instrument services: `netdata-instrumentation`
     per language named in the requirements.
   - If the requirements reference a competitor (Datadog, New Relic,
     Dynatrace, Prometheus remote-write): `netdata-migration`.
   See [`rules/composing-skills.md`](./rules/composing-skills.md) for
   the decision matrix.
5. **Produce the bundle.** Emit files in the layout specified by
   [`rules/deliverable-bundle.md`](./rules/deliverable-bundle.md).
   Each file must be valid standalone: the customer may apply them
   one at a time.
6. **Write the verification playbook** inside the bundle. Short,
   copy-pasteable commands the customer runs after applying the
   configs. Never include credentials. Use placeholders like
   `<NETDATA_HOST>` and `<BEARER_TOKEN>` and explain them in the
   bundle's `README.md`.
7. **Return the bundle manifest in chat.** Briefly list the files
   produced, flag the count of open questions, and name the highest
   priority blockers. Do not re-explain the content of the files.

## Common mistakes

- **Paraphrasing a sibling skill's content.** The sibling rules already
  teach the receiver config, the Collector pipeline, and the SDK wiring.
  Copying their prose into the bundle drifts out of sync the first time
  a sibling updates. Link to them instead; the bundle's `README.md` is
  the right place for cross-references.
- **Silently defaulting missing values.** If the requirements do not
  name a TLS mode, the bundle is not "TLS off by default." It carries
  an open question "TLS: required? cert source? MTLS required?" and the
  `otel.yaml` line is commented out with a pointer to that question.
- **Producing the bundle as chat output.** The deliverable is a folder
  of files the customer can hand to their platform team. Emit real
  files (via tool calls). Chat output is a manifest plus summary, not
  the configs themselves.
- **Running verification commands.** This skill does not have access to
  the customer's systems. Verification commands live *inside* the
  bundle as a runbook the customer executes.
- **Firing this skill when the user has live access.** If the user is
  in a shell session with their Netdata reachable, they should use the
  sibling skills directly; those can verify. This skill is for the
  written-spec-in, files-out workflow.
- **Producing a single monolithic YAML.** Split by concern: receiver
  config, Collector pipeline, per-language handoff, verification. The
  customer's platform, app, and ops teams each read different files.

## Verification

This skill's output is a filesystem bundle and a chat manifest. Verify
locally before handing it to the account team:

1. **Structural check.** Every file listed in the manifest exists.
   `open-questions.md` is non-empty unless the requirements document
   was uncharacteristically complete.
2. **YAML lint.** Each `.yaml` file in the bundle passes a basic lint
   (for example `yamllint` or `python -c "import yaml; yaml.safe_load(open('<file>'))"`).
3. **Self-contained.** The customer's platform team can follow
   `README.md` inside the bundle without reading this skill. If a file
   references external documentation, it links with an absolute URL,
   not `../../rules/...` paths that only make sense inside this repo.
4. **Ambiguity coverage.** Every category in
   [`rules/extract-requirements.md`](./rules/extract-requirements.md)
   has either a filled value in the bundle or an entry in
   `open-questions.md`. Silent defaults are a defect.

The account team then verifies the bundle *with the customer* before
production application. Do not treat "agent produced a bundle" as
"customer can install." The open-questions pass through a human before
the configs hit a real cluster.

## References

- [`rules/extract-requirements.md`](./rules/extract-requirements.md)
- [`rules/deliverable-bundle.md`](./rules/deliverable-bundle.md)
- [`rules/composing-skills.md`](./rules/composing-skills.md)
- Sibling: [`netdata-otel-setup`](../netdata-otel-setup/)
- Sibling: [`netdata-collector-config`](../netdata-collector-config/)
- Sibling: [`netdata-instrumentation`](../netdata-instrumentation/)
- Sibling: [`netdata-migration`](../netdata-migration/)
- OpenTelemetry Collector deployment patterns: https://opentelemetry.io/docs/collector/deployment/
- Netdata OTLP integration: https://learn.netdata.cloud/docs/collecting-metrics/opentelemetry
