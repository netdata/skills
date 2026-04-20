# Deliverable bundle

## Scope

The canonical folder layout the skill produces. Every bundle looks the
same so the customer's platform team can apply files in a predictable
order.

## Folder layout

```text
<customer-or-project-name>-netdata-bundle/
  README.md                    # How to apply the bundle, in order
  open-questions.md            # Unresolved inputs, account team to chase
  netdata/
    otel.yaml                  # Netdata agent receiver config
    claim.sh                   # Optional: Cloud claim command if in scope
  collector/
    values.yaml                # OTel Collector Helm values or equivalent
    collector-config.yaml      # Pipeline definition
  instrumentation/
    <language>.md              # One file per language in stack inventory
  verify.md                    # Post-install verification runbook
```

Any subsection the requirements do not activate is omitted. A bundle
for a direct-OTLP customer with no Collector has no `collector/`
directory. A bundle for a metrics-only customer has no log wiring
snippets in the language handoffs.

## File-by-file contract

### `README.md`

The single entry point. Must stand on its own without the customer
reading this skill's source.

Sections:
1. What this bundle contains.
2. Application order: which file first, which next.
3. Placeholders in the bundle and where to fill them
   (`<NETDATA_HOST>`, `<BEARER_TOKEN>`, `<CERT_PATH>`).
4. Link to the account team contact for open questions.
5. Link to `verify.md`.

Maximum length: 150 lines. Longer means the bundle is doing the
reading for the customer.

### `open-questions.md`

A table with three columns: Question, Why it matters, Assumed default.

Rows come from the extraction pass. Sort by severity: blockers first
(TLS posture, auth, compliance), then sizing, then stylistic choices.

One question per row. No compound questions.

### `netdata/otel.yaml`

The receiver config. Derived by delegating to
[`netdata-otel-setup`](../../netdata-otel-setup/). Comments in the file
cite the specific rule file for each non-default setting, so the
customer's platform team can verify the skill did not invent a knob.

Example comment style:

```yaml
logs:
  # Rotation defaults documented in
  # netdata-otel-setup/rules/log-ingestion.md. Adjust only if
  # volume estimates in open-questions.md change.
  number_of_journal_files: 10
```

### `netdata/claim.sh`

Present only if the requirements name Netdata Cloud as a target.
Shebanged, chmod-ready, with explicit placeholders for the claim
token and room IDs. Never commit a real claim token; the script
reads `NETDATA_CLAIM_TOKEN` from the environment.

### `collector/values.yaml` and `collector/collector-config.yaml`

Collector-side config. Derived by delegating to
[`netdata-collector-config`](../../netdata-collector-config/).

Split by concern:
- `values.yaml`: chart values for the customer's package manager
  (Helm, Operator, plain YAML). Contains the deployment pattern
  choice (DaemonSet, gateway, Operator).
- `collector-config.yaml`: the actual pipeline (receivers, processors,
  exporters). This is the file the customer edits most often; keep
  it separate so values.yaml can be regenerated without losing
  pipeline tweaks.

### `instrumentation/<language>.md`

One Markdown file per language named in the requirements stack
inventory. Derived from
[`netdata-instrumentation`](../../netdata-instrumentation/).

Each file contains:
1. Package install command.
2. Minimal SDK init snippet the customer's devs copy-paste.
3. Environment variables to set in production.
4. Verification command the dev runs before merging.

This is *handoff* content, not live instrumentation. The customer's
devs take the file, paste the init code into their repo, and run the
verification step themselves. The bundle does not assume anyone with
access to this skill will run the code.

### `verify.md`

A short, linear runbook the customer's ops team runs after applying
the bundle.

Every step:
- One or two commands, copy-pasteable.
- Expected output as a literal block, or an MCP-query prompt the
  customer's own agent can run against their Netdata.
- "If you see X instead" troubleshooting pointers, linking to
  `netdata-otel-setup/rules/troubleshooting.md` by absolute URL.

Maximum length: 100 lines. Longer means verification is too complex
and the config needs to be simpler.

## File format rules

**Incorrect** (dumps all config into one monolithic file):

```text
customer-bundle/
  everything.yaml
```

**Correct** (split by team that owns the change):

```text
customer-bundle/
  netdata/otel.yaml          # platform team applies on Netdata hosts
  collector/values.yaml      # platform team applies to K8s
  instrumentation/python.md  # app team copies snippet into repo
```

**Incorrect** (relative links into this skills repo that break when
the bundle is handed to the customer):

```markdown
See [../../../skills/netdata-otel-setup/rules/tls-and-auth.md] for
TLS options.
```

**Correct** (absolute URL to the public location or inline the
relevant snippet):

```markdown
See https://github.com/netdata/skills/blob/main/skills/netdata-otel-setup/rules/tls-and-auth.md
for TLS options. The knobs most relevant to this bundle:

- `endpoint.tls_cert_path`
- `endpoint.tls_key_path`
- `endpoint.tls_ca_cert_path`
```

## Naming

Bundle folder: `<customer-slug>-netdata-bundle` if the customer name
is given. Otherwise `netdata-bundle` in the working directory. The
agent asks once at the start of the conversation if the customer name
is missing from the requirements document.

No dates in the folder name. Version lives in the bundle's `README.md`
frontmatter if the customer wants it; the folder name stays stable
across revisions.

## What the bundle is not

- Not a replacement for the platform team's internal review. The
  customer's team must read every file before applying.
- Not a complete Netdata deployment. It assumes the customer already
  has Netdata reachable on the target host.
- Not a migration runbook. Migration-specific guidance comes from
  [`netdata-migration`](../../netdata-migration/) and lives in a
  `migration.md` at the bundle root when the requirements indicate
  moving off another vendor.
