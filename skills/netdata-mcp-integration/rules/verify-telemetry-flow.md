# Verify telemetry flow via MCP

## When to run this

Right after adding or changing instrumentation, or after changing
mapping files under `/etc/netdata/otel.d/v1/metrics/`. Goal: confirm
the pipeline from producer to Netdata works, without opening a
dashboard.

## Pattern 1: service presence check

Ask the agent:

```text
Use list_metrics with filter service.name="<service>" and return the
first three contexts. If the result is empty, say so explicitly.
```

If empty, the producer is not reaching Netdata. Next step: run the
otel-setup troubleshooting ladder.

## Pattern 2: sample count in last N seconds

The canonical verification pattern used by this repo's CI:

```text
Use query_metrics to fetch the last 60 seconds of the first HTTP
server metric from service.name="<service>". Report the total sample
count. Fail if it is zero.
```

The agent translates this into a `query_metrics` call with a time
range. A non-zero sample count confirms metrics are flowing at the
expected rate.

## Pattern 3: dimension sanity

After adding a mapping file, confirm the dimension names came out
right:

```text
Call get_metrics_details for context <metric>.<service> and list all
dimension names. They should match the values of the attribute named
in dimension_attribute_key in the mapping file.
```

If the dimension names look like raw numbers or random ids, the
mapping's `dimension_attribute_key` is pointing at a high-cardinality
attribute. Pick a different key.

## Pattern 4: end-to-end smoke via JSON-RPC

For CI or non-agent verification, hit the MCP HTTP endpoint directly.
The canonical runnable version is shipped in this repo at
[`tests/e2e/verify-metrics.py`](../../../tests/e2e/verify-metrics.py).

The minimal call shape:

```bash
TOKEN="$(sudo cat /var/lib/netdata/mcp_dev_preview_api_key)"

# 1. Initialize session
curl -sS -X POST "http://localhost:19999/mcp" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"verify","version":"0.1.0"}}}'

# 2. List tools (should return 13 entries)
curl -sS -X POST "http://localhost:19999/mcp" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'

# 3. Call a tool
curl -sS -X POST "http://localhost:19999/mcp" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "list_metrics",
      "arguments": {}
    }
  }'
```

## Fallback via REST

If the MCP transport is flaky or not yet wired, the Netdata REST API
gives similar data. Use for quick checks, not as the long-term
verification path:

```bash
curl -s 'http://localhost:19999/api/v2/contexts' \
  | jq --arg svc "$OTEL_SERVICE_NAME" \
       '.contexts | to_entries[] | select(.key | contains($svc))'
```

## What "works" looks like

- `list_metrics` returns at least one context whose name or attribute
  set contains the expected `service.name`.
- `query_metrics` for that context returns data points within the
  last two collection intervals (default 10s each, so within the
  last 20s).
- `find_anomalous_metrics` against the same service does not flag
  zero-cardinality metrics as anomalous.

If any of these fails, return to the otel-setup troubleshooting
ladder; the issue is on the ingestion side, not the query side.
