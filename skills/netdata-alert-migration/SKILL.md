---
name: netdata-alert-migration
description: Use when migrating alerting rules from VictoriaMetrics (vmalert), Prometheus, Thanos Ruler, or Mimir/Cortex to Netdata health alerts. These tools share the same Prometheus alerting-rule YAML and PromQL/MetricsQL, so the method is identical. Covers the stock-first decision (Netdata already ships alerts for most common signals), the translation methodology from PromQL expressions to Netdata lookup/calc/warn/crit on a chart context, the constructs that do not map cleanly (cross-metric joins, predict_linear, histogram_quantile, fleet aggregations, absent), notification-routing parity with Alertmanager (agent roles and Netdata Cloud), and automatic verification over MCP. Pairs with netdata-mcp-integration to connect and netdata-custom-collector when a rule alerts on a metric Netdata does not yet collect.
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - migration
  - alerts
  - victoriametrics
  - vmalert
  - prometheus
  - alertmanager
---

# Netdata alert migration

This skill migrates alerting rules to Netdata's health engine. The
source is almost always a Prometheus-style rule set: VictoriaMetrics
`vmalert`, Prometheus itself, Thanos Ruler, or Mimir/Cortex. They all
consume the same alerting-rule YAML and the same PromQL/MetricsQL
query language, so one method covers all of them. Examples here lead
with `vmalert` because that is the common request.

The work is not a transpile. The two systems have different models:
a PromQL rule queries arbitrary time series by metric name and label
matchers, while a Netdata alert attaches to a chart context and
aggregates that chart's dimensions over a time window. There is no
one-to-one converter. This skill is a translation methodology, and a
large part of it is recognizing what you should not translate at all.

## When to use this skill

- The user is moving off VictoriaMetrics, Prometheus, Thanos, or
  Mimir and wants their alerting rules reproduced in Netdata.
- The user has a `vmalert` rules file or a Prometheus
  `*.rules.yaml` and asks how to get the same alerts in Netdata.
- The user wants their Alertmanager notification routing reproduced
  in Netdata.
- The user asks which of their existing alerts Netdata already
  covers out of the box.

## Key facts

- **Stock-first.** Netdata ships 137 stock health files covering the
  bulk of what node_exporter-style rule sets alert on: CPU, memory,
  OOM, disk space and inode exhaustion, disk fill prediction, load,
  file descriptors, certificate expiry, ping and HTTP checks, MySQL,
  PostgreSQL, Redis, Kubernetes, and 5xx rates. For these, do not
  translate. Enable or tune the stock alert. See
  [`rules/stock-alert-equivalents.md`](./rules/stock-alert-equivalents.md).
- **Model gap.** PromQL selects series by `name{label=...}`; Netdata
  binds an alert to a context (`on:`) and reads that chart's
  dimensions through `lookup:`. A per-series Prometheus alert usually
  becomes a Netdata `template:` (one alert per chart instance) plus
  `lookup ... of <dimensions>`. The target DSL is in
  [`rules/netdata-health-alerts.md`](./rules/netdata-health-alerts.md).
- **What translates cleanly.** A single-metric threshold with `for:`
  maps to `lookup` over a window plus `warn:`/`crit:` with the
  hysteresis idiom and an optional `delay:`. The field-by-field
  mapping and worked examples are in
  [`rules/translate-rules.md`](./rules/translate-rules.md).
- **What does not.** Cross-metric joins (`on`/`group_left`),
  forecasting (`predict_linear`), `histogram_quantile`, fleet-wide
  aggregations (`sum`/`topk by`), and `absent()`/`up == 0` have no
  per-chart equivalent. Each needs a strategy, not a transcription.
  See [`rules/hard-cases.md`](./rules/hard-cases.md).
- **Collect-first.** A rule can only become a Netdata alert if Netdata
  collects the metric it references, as a chart context with the right
  dimensions. If it does not, either collect it first (the
  `netdata-custom-collector` skill) or keep that subset on `vmalert`.
- **Recording rules usually do not migrate.** They precompute
  expressions for performance. Netdata evaluates alerts at the source
  against raw charts, so a standalone recording rule is dropped; if an
  alert's `expr` references a recorded metric, inline that expression.
- **Notifications.** Alertmanager `route`/`receiver` maps to Netdata
  notification roles (agent) or Netdata Cloud integrations and
  silencing rules. Cloud is the closer parity for label-matcher
  routing. Some Alertmanager features (`group_by`, group timing,
  `inhibit_rules`) have no clean equivalent. See
  [`rules/notifications.md`](./rules/notifications.md).

## Step-by-step

1. **Inventory** the source rules. Separate alerting rules from
   recording rules; drop or inline the recording rules.
2. **Classify each alerting rule** with the decision tree in
   [`rules/choose-what-to-migrate.md`](./rules/choose-what-to-migrate.md):
   stock equivalent, clean translation, hard case, or
   metric-not-collected.
3. **For stock-covered signals**, enable or tune the stock alert per
   [`rules/stock-alert-equivalents.md`](./rules/stock-alert-equivalents.md).
   Do not hand-write these.
4. **For clean translations**, write the Netdata alert following
   [`rules/translate-rules.md`](./rules/translate-rules.md), using the
   DSL reference in
   [`rules/netdata-health-alerts.md`](./rules/netdata-health-alerts.md).
5. **For hard cases**, apply the strategy in
   [`rules/hard-cases.md`](./rules/hard-cases.md) (native equivalent,
   collect-first, redesign, or keep on `vmalert`). Flag anything that
   cannot be reproduced.
6. **Map notification routing** per
   [`rules/notifications.md`](./rules/notifications.md).
7. **Verify** automatically over MCP using
   [`rules/verify-migration.md`](./rules/verify-migration.md): confirm
   each alert loaded, attached, and parsed, then trigger a transition
   and revert. When a Netdata MCP server is connected, do this without
   waiting for the user.

## Common mistakes

- Hand-translating an alert Netdata already ships. Always check the
  stock library first; tuning a stock alert is a one-line change.
- Treating the translation as a syntax conversion. The data model is
  different; you choose a context and dimensions, not transcribe an
  expression.
- Translating a rule whose metric Netdata does not collect. The alert
  will parse but never attach. Collect the metric first.
- Reproducing `for: 5m` as if it were exact. Netdata has no `for`;
  approximate it with the `lookup` window and `delay:`.
- Emitting `families:` or `charts:` lines, or starting from the old
  documented DSL. Those keys are silently ignored. Model new alerts
  on current stock files.
- Promising Alertmanager parity for `group_by`, group timing, or
  `inhibit_rules`. State the gap instead.
- Declaring the migration done without confirming the alerts loaded
  and evaluate. Verify over MCP.

## Verification

When a Netdata MCP server is connected, the agent verifies the
migration itself rather than handing the user a checklist. After
`netdatacli reload-health`, call `list_running_alerts` to confirm each
translated alert is present and attached (not `UNINITIALIZED` or
`UNDEFINED`), cross-check the parsed expression via
`GET /api/v1/alarms?all`, then deliberately trigger one alert (lower a
threshold), confirm the transition with `list_alert_transitions`, and
revert. A health file that fails to parse is skipped, not fatal, so a
missing alert means a parse or attach error: check the daemon log
(`journalctl -u netdata`). Full procedure in
[`rules/verify-migration.md`](./rules/verify-migration.md).

## References

- [`rules/choose-what-to-migrate.md`](./rules/choose-what-to-migrate.md)
- [`rules/stock-alert-equivalents.md`](./rules/stock-alert-equivalents.md)
- [`rules/netdata-health-alerts.md`](./rules/netdata-health-alerts.md)
- [`rules/translate-rules.md`](./rules/translate-rules.md)
- [`rules/hard-cases.md`](./rules/hard-cases.md)
- [`rules/notifications.md`](./rules/notifications.md)
- [`rules/verify-migration.md`](./rules/verify-migration.md)
- Netdata health reference: `src/health/REFERENCE.md` in the Netdata repo.
- vmalert: https://docs.victoriametrics.com/victoriametrics/vmalert/
- Prometheus alerting rules: https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/
- Alertmanager config: https://prometheus.io/docs/alerting/latest/configuration/
