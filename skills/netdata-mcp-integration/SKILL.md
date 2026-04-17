---
name: netdata-mcp-integration
description: Use when an AI coding agent needs to connect to a Netdata Agent, Parent, or Netdata Cloud via MCP to verify telemetry, query live metrics, cross-reference instrumentation with infrastructure signals, or troubleshoot services. Covers Claude Code, Cursor, Codex, and Gemini CLI client configs for both local (http://HOST:19999/mcp) and Netdata Cloud endpoints.
version: 0.1.0
author: Netdata
license: Apache-2.0
tags:
  - netdata
  - mcp
  - model-context-protocol
  - claude-code
  - cursor
  - codex
  - gemini-cli
  - telemetry-verification
---

# Netdata MCP integration

This skill points an AI coding agent at a Netdata instance's MCP server
so it can list metrics, query live data, inspect alert state, and
verify that instrumentation changes are producing the expected
telemetry.

## When to use this skill

- The user wants their agent to see live infrastructure signals.
- The user just added OTel instrumentation and wants to confirm
  metrics arrived without opening the dashboard.
- The user is debugging a service and wants the agent to correlate
  application telemetry with host-level signals (CPU, memory, disk).
- The user is setting up Claude Code, Cursor, Codex, or Gemini CLI for
  the first time against Netdata.

## Key facts

- MCP endpoint is served by every Netdata Agent, Parent, or Cloud on
  the same port as the dashboard (default `19999`).
- Two URL paths: `/mcp` (HTTP streamable and WebSocket) and `/sse`
  (Server-Sent Events). Both live under
  `http://HOST:19999`. For WebSocket, use `ws://HOST:19999/mcp`.
- Transports supported: HTTP streamable (default on `/mcp`), SSE,
  WebSocket, and stdio via the `nd-mcp` bridge binary.
- Auth: bearer token via the header `Authorization: Bearer <token>`.
  The token is a UUID Netdata generates at first start, stored at
  `/var/lib/netdata/mcp_dev_preview_api_key` (native installs) or
  `/opt/netdata/var/lib/netdata/mcp_dev_preview_api_key` (static).
- No user/password auth. No per-tool permission grants. A bearer
  token is all-or-nothing.
- The `nd-mcp` bridge is bundled with Netdata. Paths:
  `/usr/bin/nd-mcp` (native), `/opt/netdata/usr/bin/nd-mcp`
  (static), `/usr/local/netdata/usr/bin/nd-mcp` (macOS source),
  `C:\Program Files\Netdata\usr\bin\nd-mcp.exe` (Windows).
- 13 active MCP tools. By category:
  - Discovery: `list_metrics`, `get_metrics_details`, `list_nodes`,
    `get_nodes_details`, `list_functions`.
  - Query: `query_metrics`.
  - Analysis: `find_correlated_metrics`, `find_anomalous_metrics`,
    `find_unstable_metrics`.
  - Alerts: `list_raised_alerts`, `list_running_alerts`,
    `list_alert_transitions`.
  - Side effects: `execute_function` (the only write-ish tool;
    marked open-world).

## Step-by-step

1. Pick the right Netdata to connect to:
   - A **Parent node** gives visibility across every child streaming
     to it. Best choice for an agent that needs the broadest view.
   - A **Child/standalone Agent** gives visibility into that one host.
     Fine for local dev or single-server setups.
   - **Netdata Cloud** MCP is not yet generally available at the time
     of this release; check the Netdata docs before relying on it.

2. Read the API key off the target host:

   ```bash
   sudo cat /var/lib/netdata/mcp_dev_preview_api_key
   # or, for static installs:
   sudo cat /opt/netdata/var/lib/netdata/mcp_dev_preview_api_key
   ```

3. Configure the agent's MCP client. Pick the transport that matches
   what the agent supports (see the `rules/` per-client files).

4. Restart the agent so it reads the new config.

5. Verify the connection lists the 13 tools (see Verification).

6. Ask the agent a probe question that exercises `list_metrics` or
   `query_metrics`. A plain "what metrics is service X emitting right
   now?" is usually enough.

## Common mistakes

- Using the dashboard URL (`http://HOST:19999`) as the MCP endpoint.
  The MCP endpoint is `http://HOST:19999/mcp` (add the path).
- Forgetting the bearer token. The HTTP transport returns 401 and
  the agent sees a generic connection error.
- Mixing transports in the config. A client that wants
  HTTP-streamable must use `http://`; a WebSocket client must use
  `ws://`. The `nd-mcp` bridge internally speaks any of them,
  selected by the URL scheme.
- Pointing the agent at a child when the question spans the whole
  fleet. Ask the parent.
- Treating `execute_function` as read-only. That tool can restart
  services, kill processes, change alert state, and so on depending
  on the function. Know which functions the Agent allows before
  approving calls.

## Verification

After configuring the agent, run a minimum-connectivity probe.

For Claude Code:

```bash
claude mcp list
# Expect to see "netdata" listed.
```

Or ask the agent directly:

```text
List the 13 tools available from the netdata MCP server.
```

The expected names are listed in Key facts above.

Then a real query:

```text
Call list_metrics and filter by attribute service.name equal to
"checkout". Return the first five contexts.
```

A non-empty result confirms the agent can query the target Netdata.

For a non-agent probe (useful in CI), the same pattern works with
`curl` against the HTTP-streamable endpoint:

```bash
TOKEN="$(sudo cat /var/lib/netdata/mcp_dev_preview_api_key)"
curl -sS -X POST "http://localhost:19999/mcp" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  | jq '.result.tools[].name'
```

The canonical verification script shipped with this repo is at
[`tests/e2e/verify-metrics.py`](../../tests/e2e/verify-metrics.py). It
speaks the same JSON-RPC dialect and is used by CI to confirm the
whole ingestion pipeline works end to end.

## References

- [`rules/connect-claude-code.md`](./rules/connect-claude-code.md)
- [`rules/connect-cursor.md`](./rules/connect-cursor.md)
- [`rules/connect-codex.md`](./rules/connect-codex.md)
- [`rules/verify-telemetry-flow.md`](./rules/verify-telemetry-flow.md)
- [`rules/query-patterns.md`](./rules/query-patterns.md)
- Netdata MCP README: `src/web/mcp/README.md` in the Netdata repo.
- MCP protocol spec: https://modelcontextprotocol.io
