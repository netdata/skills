# netdata-custom-collector

Skill for getting metrics into Netdata from a target it does not
already monitor. Covers choosing the cheapest ingestion path (an
existing collector, or the built-in StatsD server) and, when code is
needed, writing a collector in any language via the external-plugin
line protocol, or the legacy python.d / charts.d frameworks.

See [SKILL.md](./SKILL.md) for agent-facing content. Rule files live under [`rules/`](./rules/).
