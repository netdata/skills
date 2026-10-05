# CI recipes

Patterns for using `netdata/skills` in automated workflows.

## Headless PR review with Claude Code

Run Claude Code in non-interactive mode against a PR. Load this skill pack so reviews are grounded in Netdata-aware guidance rather than generic code review.

```yaml
# .github/workflows/claude-review.yml
name: Claude review (Netdata skills)

on:
  pull_request:
    types: [opened, reopened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
      contents: read
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Install skills
        run: |
          mkdir -p ~/.claude/skills
          git clone https://github.com/netdata/skills ~/.claude/skills/netdata-skills

      - name: Install Claude CLI
        run: npm install -g @anthropic-ai/claude-code

      - name: Review diff
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          DIFF=$(git diff origin/${{ github.event.pull_request.base.ref }}...HEAD)
          PROMPT=$(cat <<EOF
          Review this pull request. Focus on changes to Netdata config
          (otel.yaml, otel.d/), OpenTelemetry instrumentation, or OTel
          Collector config. Flag any claim that Netdata accepts traces
          without the version caveat: only Agents built after 2026-08-17
          (nightly) or the first stable release after v2.11.1 accept
          them; stable v2.11.x does not. Flag any mapping files or
          instrumentation code that reference _nd_chart_instance or
          _nd_dimension as producer-side attributes; those are not valid.
          _nd_chart_instance does not exist in Netdata. _nd_dimension
          exists only inside Netdata's OTel consumer for histogram
          flattening; producers must not emit it.

          Diff:
          $DIFF
          EOF
          )
          claude -p "$PROMPT" > review.txt
          gh pr comment ${{ github.event.pull_request.number }} --body-file review.txt
```

## Nightly telemetry-drift check

Run a scheduled job that connects to a staging Netdata via MCP and confirms the canonical service names from the fleet are still emitting. Regressions mean somebody deployed a service whose instrumentation broke.

```yaml
name: Telemetry drift

on:
  schedule:
    - cron: '0 3 * * *'
  workflow_dispatch:

jobs:
  drift:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Claude CLI
        run: npm install -g @anthropic-ai/claude-code

      - name: Configure MCP
        run: |
          mkdir -p ~/.claude
          cat > ~/.claude/mcp.json <<EOF
          {
            "mcpServers": {
              "netdata": {
                "url": "${{ secrets.NETDATA_STAGING_MCP_URL }}",
                "headers": {
                  "Authorization": "Bearer ${{ secrets.NETDATA_MCP_TOKEN }}"
                }
              }
            }
          }
          EOF

      - name: Install skills
        run: git clone https://github.com/netdata/skills ~/.claude/skills/netdata-skills

      - name: Query via MCP
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          claude -p "Use list_metrics to enumerate every unique service.name value currently reporting to Netdata. Compare to the expected list (checkout, cart, payment, search, shipping). Fail if any expected service has had zero data points in the last hour." > drift.txt
          cat drift.txt
```

## Instrumentation parity check on deploy

Gate a deploy on "the service's old and new instrumentation are producing comparable sample counts" using a parallel-run config at the Collector.

```yaml
- name: Parity check
  run: |
    claude -p "Query Netdata via MCP. For service.name=checkout, get the http.server.request.count over the last 10 minutes from both the old and new instrumentation paths (distinguishable by service.version tag). Fail if the ratio is outside 0.8..1.2."
```

## Using the validator in CI

Already wired: `.github/workflows/validate.yml` runs `python scripts/validate.py` on every PR. To use the validator in a downstream repo that ships its own Netdata skills:

```yaml
- uses: actions/checkout@v4
  with:
    repository: netdata/skills
    path: .netdata-skills

- name: Validate local skills
  run: |
    cp -R my-skills/* .netdata-skills/skills/
    python .netdata-skills/scripts/validate.py
```
