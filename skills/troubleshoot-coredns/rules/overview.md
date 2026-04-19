# CoreDNS: Overview signals

## Scope

Signals in the Overview domain for CoreDNS, as defined in the Netdata operator playbook. Each signal
includes a short description, the collection source, and a hint for the MCP query pattern that
surfaces it. Use this file during a triage pass to decide which signal to pull first.

## Severity legend

- **HIGH**: first-class paging target. Short time to impact.
- **MEDIUM**: ticket-worthy. Usually a precursor, not a cause.
- **LOW**: context only. Useful for RCA, not for alerting.

## Signals

No structured signal list was extracted from the playbook for the Overview domain. Fall back to the
MCP discovery pattern: run `list_metrics` filtered by the CoreDNS service and inspect anything with
matching keywords.

## Triage order within this domain

Investigate HIGH-severity signals first, then MEDIUM, then LOW. HIGH-severity signals have the
shortest time to impact; a confirmed HIGH anomaly usually justifies paging. When two HIGH signals
move together, treat them as one incident until `find_correlated_metrics` rules out shared cause.

## Common false positives

- A single stale data point from a collector restart triggers many signals briefly. Re-query after
  30 seconds before escalating.
- Short bursts under 60 seconds rarely warrant action unless paired with a confirmed business
  impact.
- Comparing against yesterday's baseline on a post-deploy day produces false anomalies. Compare
  against the pre-deploy baseline.
- Collector-visible percentile latency with < 100 samples per minute is noise. Require a minimum
  sample count before acting.

## Remediation pointers

Remediation for signals in this domain is tech-specific and typically covered in the operator
playbook's SECTION 3 (Failure Patterns) or SECTION 4 (Runbooks). Before applying a change:

1. Run the MCP verification queries to record the current state.
2. Apply the smallest remediation that addresses the confirmed cause. Config changes before
   restarts; restarts before rollbacks.
3. Re-run the same MCP queries after the remediation settles. Recording before/after numbers is how
   a runbook entry gets sharpened over time.

## Netdata contexts that surface Overview

These are the real Netdata chart contexts the native collector emits for CoreDNS. Use these names
verbatim in `query_metrics` calls.

- `coredns.dns_request_count_total`: Number Of DNS Requests (requests/s). Dimensions: requests.
- `coredns.dns_responses_count_total`: Number Of DNS Responses (responses/s). Dimensions: responses.
- `coredns.dns_request_count_total_per_status`: Number Of Processed And Dropped DNS Requests
                                                (requests/s). Dimensions: processed, dropped.
- `coredns.dns_no_matching_zone_dropped_total`: Number Of Dropped DNS Requests Because Of No
                                                Matching Zone (requests/s). Dimensions: dropped.
- `coredns.dns_panic_count_total`: Number Of Panics (panics/s). Dimensions: panics.
- `coredns.dns_requests_count_total_per_proto`: Number Of DNS Requests Per Transport Protocol
                                                (requests/s). Dimensions: udp, tcp.
- `coredns.dns_requests_count_total_per_ip_family`: Number Of DNS Requests Per IP Family
                                                    (requests/s). Dimensions: v4, v6.
- `coredns.dns_requests_count_total_per_per_type`: Number Of DNS Requests Per Type (requests/s).
                                                   Dimensions: a, aaaa, mx, soa, cname, ptr.
- `coredns.dns_responses_count_total_per_rcode`: Number Of DNS Responses Per Rcode (responses/s).
                                                 Dimensions: noerror, formerr, servfail, nxdomain,
                                                 notimp, refused.
- `coredns.server_dns_request_count_total`: Number Of DNS Requests (requests/s). Dimensions:
                                            requests.
- `coredns.server_dns_responses_count_total`: Number Of DNS Responses (responses/s). Dimensions:
                                              responses.
- `coredns.server_request_count_total_per_status`: Number Of Processed And Dropped DNS Requests
                                                   (requests/s). Dimensions: processed, dropped.

## MCP query examples for this domain

```text
# Pull every context in this domain at once
query_metrics with contexts=[coredns.dns_request_count_total, coredns.dns_responses_count_total, coredns.dns_request_count_total_per_status, coredns.dns_no_matching_zone_dropped_total, coredns.dns_panic_count_total, coredns.dns_requests_count_total_per_proto] and relative_window=-30m

# Rank anomalies that match this domain
find_anomalous_metrics with node=<host> and context_pattern="coredns.*"

# Correlate a problem context with others outside the domain
find_correlated_metrics around the incident window, anchor_context="coredns.dns_request_count_total"
```

## When to escalate out of this skill

If none of the signals in this domain move during the incident, the root cause is elsewhere. Typical
re-routing:

- Host-resource domain: load, CPU, memory, disk, network saturation
- Dependency domain: the service's upstream or downstream (database, cache, queue) is the actual
  source
- Orchestrator domain: Kubernetes or systemd lifecycle events rather than application misbehavior
- Alert engine domain: a misconfigured alert threshold triggered a false-positive incident
