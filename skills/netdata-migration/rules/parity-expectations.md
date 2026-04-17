# Parity expectations

## Things that carry over directly

- **Metric names written in code**: custom counters, gauges, and
  histograms with names you control. Pick the OTel Meter API and
  keep the same names.
- **Service name / environment / version**: `service.name`,
  `deployment.environment`, `service.version`. Every vendor uses
  some variant; map once, forget.
- **Host-level signals** (CPU, memory, disk, network, filesystem).
  Available via hostmetrics receiver or Netdata's native
  collectors. No instrumentation work required.
- **Prometheus metrics**: whichever path you pick (Netdata native
  or OTel Collector), the samples land in Netdata with their
  Prometheus labels preserved as attributes.

## Things that carry over with rework

- **Alerts**: every vendor has a different rule language. Expect
  to rewrite. Prioritize by frequency of firing and by business
  impact, not by count. Many alerts copied from old
  configurations were never actually useful; a migration is a
  good time to prune.
- **Dashboards**: curated dashboards need rebuilding. Netdata's
  auto-generated dashboards cover most ad-hoc needs; curated
  dashboards tend to be a smaller set than the pre-migration
  stack.
- **Log queries**: each vendor has a different query syntax.
  Netdata's Logs tab uses systemd journal queries.

## Things that do not carry over

- **Trace exploration**: Netdata does not accept traces yet.
  Route traces to a different backend during the migration
  window. Plan a second migration for traces when Netdata trace
  support lands.
- **RUM and Synthetics**: outside Netdata's scope. Keep or replace
  independently.
- **Vendor-specific AI/ML features** (Watchdog, Davis,
  Predictive Alerting). Netdata has its own anomaly detection
  exposed via `find_anomalous_metrics` and `find_unstable_metrics`
  MCP tools; the UX is different.
- **Historical data replay**. There is no tool to backfill old
  vendor data into Netdata. Retention starts at the cutover date.

## A good migration is a prune

Most teams carry four to ten years of accumulated vendor config
they never audit. A migration is the right moment to:

- Turn off custom metrics nobody queries.
- Delete alerts that have not fired in 12 months and have no
  owner.
- Consolidate dashboards with overlapping content.
- Rename services to match a single convention.

Do the prune before rebuilding on Netdata. Building a 1:1 copy
of a messy old setup loses the one benefit of the migration.

## Validation checklist

Before decommissioning the old vendor:

- [ ] Every currently-firing alert has a Netdata equivalent
      actively monitoring.
- [ ] Every pager-grade dashboard has been rebuilt.
- [ ] MCP `list_metrics` shows all `service.name` values from the
      old vendor's metric explorer.
- [ ] Ingest rates in Netdata are within 10% of the old vendor
      for a comparable time window.
- [ ] On-call has validated the Netdata runbooks against at least
      one drill.

Only then: turn off the old vendor agent.

## A note on the parallel-run window

Teams underestimate how long a parallel run should last. The
useful lower bound is **one full weekly cycle plus one change
window**. Short versions of this bound are "one week" or "one
Tuesday change"; neither is enough. A real parallel run needs to
cover:

- At least one on-call rotation.
- At least one normal deploy.
- At least one quiet period (weekend or holiday).

Cutovers that skip this window almost always discover a gap the
first time the system has a real production issue.
