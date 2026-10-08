# Composing with sibling skills

## Scope

This skill does not paraphrase the other Tier 1 skills. It composes
them. This rule explains *which* sibling fires for *which* section of
the bundle, and how to keep the bundle in sync with the sibling's
authoritative content.

## Decision matrix

Each row below maps one bundle slot to the sibling rule that owns it.
Format: **slot** (trigger) → sibling rule → bundle file.

Receiver side (owned by `netdata-otel-setup`):

- **Receiver config** (always) →
  `rules/enable-otlp-receiver.md` → `netdata/otel.yaml`.
- **TLS on receiver** (customer names TLS as required or preferred) →
  `rules/tls-and-auth.md` → inline in `netdata/otel.yaml`.
- **Log ingestion** (customer names logs in scope) →
  `rules/log-ingestion.md` → inline in `netdata/otel.yaml`.
- **Trace ingestion** (customer names traces, APM, or distributed
  tracing in scope) → `rules/trace-ingestion.md` → inline in
  `netdata/otel.yaml`, plus a `traces` pipeline in
  `collector/collector-config.yaml`. Traces need a Netdata Agent built
  after 2026-08-17 (nightly) or the first stable release after
  v2.11.1; when the customer's Agent version is unknown, raise it as
  an open question.
- **Cloud claim** (customer targets Netdata Cloud) →
  `rules/enable-otlp-receiver.md` → `netdata/claim.sh`.

Collector side (owned by `netdata-collector-config`):

- **DaemonSet** (K8s, per-node pattern) →
  `rules/daemonset-deployment.md` → `collector/values.yaml`.
- **Gateway** (central aggregation named) →
  `rules/gateway-deployment.md` → `collector/values.yaml`.
- **OTel Operator** (auto-instrumentation via Operator named) →
  `rules/otel-operator.md` → `collector/values.yaml`.
- **Processors** (attribute allowlists, batch tuning) →
  `rules/processors.md` → `collector/collector-config.yaml`.
- **Netdata exporter** (always when Collector is in bundle) →
  `rules/exporters-to-netdata.md` → `collector/collector-config.yaml`.

Producer side and migration:

- **Language handoff** (each language in stack inventory) →
  `netdata-instrumentation/rules/<lang>.md` →
  `instrumentation/<lang>.md`.
- **Migration plan** (competitor named in requirements) →
  `netdata-migration/rules/from-<vendor>.md` →
  `migration.md` at bundle root.

## Composition rules

### Rule 1: cite, do not paraphrase

Each generated file includes a comment block pointing to the source
rule. The rule owns the truth; the bundle references it.

**Incorrect** (rewrites the sibling's prose inside the bundle):

```yaml
# otel.yaml
# OTLP log ingestion is always on once otel-plugin is running.
# Ingested records are indexed under /var/log/netdata/otel/v2.
# Retention knobs live under logs.retention.default.
# ... three more paragraphs ...
logs:
  retention:
    default:
      max_total_size: "10GB"
```

**Correct** (points at the authoritative rule, keeps the config
minimal):

```yaml
# otel.yaml
# Log ingestion path and rotation documented in
# https://github.com/netdata/skills/blob/main/skills/netdata-otel-setup/rules/log-ingestion.md
logs:
  retention:
    default:
      max_total_size: "10GB"
```

### Rule 2: the sibling's examples are the bundle's seed

When a sibling rule ships a complete example (for example the minimal
`otel.yaml` in `netdata-otel-setup/rules/enable-otlp-receiver.md`),
use it as the bundle's starting point. Only diverge to honor an
explicit requirement. Every divergence carries a comment pointing at
the requirement it serves.

### Rule 3: one sibling per file, whenever possible

`netdata/otel.yaml` is governed by `netdata-otel-setup`. If a bundle
section pulls from two siblings, split the file. For example, a
migration bundle that wires the Collector for dual-write during a
Prometheus cutover keeps the Collector bits in `collector/` (owner:
`netdata-collector-config`) and the migration narrative in
`migration.md` (owner: `netdata-migration`). Do not interleave.

### Rule 4: language handoffs come from the instrumentation skill verbatim

The language-specific init code in `netdata-instrumentation/rules/<lang>.md`
is verified in the E2E harness for Python today, with Java and
Node.js planned. When producing `instrumentation/<lang>.md` in the
bundle, paste the sibling rule's minimal-init fenced block as-is.
Do not edit it. The fixture-rule sync contract in
`CONTRIBUTING.md` applies transitively: if the bundle's snippet drifts
from the sibling rule, either the sibling is wrong or the bundle is
wrong. The sibling wins.

### Rule 5: skip the skill if the requirement is absent

If the requirements do not mention logs, the bundle does not ship a
logs section. If the requirements do not mention Kubernetes, the
bundle has no Collector files. Scope is set by the requirements, not
by completeness.

The exception: `netdata-otel-setup` always fires. Every bundle ships
an `otel.yaml`, even if minimal, so the customer's platform team has
an explicit starting point.

## When the requirements contradict a sibling skill

If the requirements specify something the sibling rule says not to do
(for example: "suffix `/v1/metrics` on the gRPC endpoint" when the
`nodejs.md` rule says do not), the bundle:

1. Flags the contradiction in `open-questions.md` as a blocker.
2. Defaults to the sibling's recommendation in the YAML.
3. Includes a comment in the relevant file pointing at the
   contradiction.

The customer's platform team resolves the conflict, not the agent.

## Cross-references inside the bundle

The bundle's internal links (for example `README.md` pointing at
`verify.md`) are relative within the bundle folder. Links out of the
bundle (to the sibling skills in this repo) are absolute URLs to the
public repository, so the customer can follow them without cloning
anything.

## What this rule is not

- Not a sibling skill catalog. See the root `README.md` for the
  directory of Tier 1 skills.
- Not a deep guide to each sibling's content. That content lives in
  each sibling's `SKILL.md` and `rules/`. This rule only points at
  the right sibling for each slot.
