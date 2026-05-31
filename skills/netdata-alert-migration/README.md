# netdata-alert-migration

Skill for migrating alerting rules from VictoriaMetrics (vmalert),
Prometheus, Thanos Ruler, or Mimir/Cortex to Netdata health alerts.
Covers the stock-first decision, the PromQL-to-Netdata translation
methodology, the constructs that do not map cleanly, notification
routing parity with Alertmanager, and automatic verification over MCP.

See [SKILL.md](./SKILL.md) for agent-facing content. Rule files live under [`rules/`](./rules/).
