# Skills + MCP architecture

How this skill pack fits together with Netdata's MCP server.

## The two pipes

```
 user prompt                                            live infra state
      |                                                         |
      v                                                         |
+-----------+        +------------------+                       |
| agent     | <----- | netdata/skills   |                       |
| (CC/Cursor|  load  | (this repo)      |                       |
|  /Codex/  |        +------------------+                       |
|  Gemini)  |                                                   |
|           |        +------------------+     +---------------+ |
|           | <----> | Netdata MCP      | <-> | Netdata Agent | |
|           |  JSON  | /mcp (HTTP/SSE/  |     | (local or     | |
|           |   RPC  |  WS or stdio via |     |  Parent or    | |
+-----------+        |  nd-mcp bridge)  |     |  Cloud)       | |
                     +------------------+     +---------------+ |
                                                                |
                                                           +----+
                                                           | infra
                                                           +----
```

Two pipes flow into the agent:

1. **Instructions**: what to do with a user request. Provided by the skill pack you cloned (this repo). Skills are YAML+Markdown files; the agent matches `description` fields against the prompt.

2. **State**: live telemetry from the infrastructure. Provided by the Netdata MCP server, which exposes the Agent's metrics, logs, and alerts over MCP's JSON-RPC.

The skills teach the agent how to use the state pipe. A skill says "when the user asks X, open the MCP and call `list_metrics` with filter Y". Without the state pipe, the agent is writing code blind. Without the skills, the agent sees raw tools and has to guess.

## What MCP gives the agent

13 tools (see [`../skills/netdata-mcp-integration/rules/query-patterns.md`](../skills/netdata-mcp-integration/rules/query-patterns.md) for the full list). The critical handful:

- `list_metrics` — discovery. What is being reported?
- `query_metrics` — retrieve numeric time-series.
- `find_anomalous_metrics` — rank by anomaly rate. Useful when the user says "something is off, not sure what".
- `find_correlated_metrics` — rank by co-movement. Useful when you have a known-bad signal and want to find the cause.
- `list_raised_alerts` / `list_alert_transitions` — current and historical alert state.

One write-ish tool: `execute_function`. The Netdata `functions` subsystem lets you run curated diagnostic or control commands on a node (process list, network connections, systemd actions). Always user-gate.

## What MCP does NOT give the agent

- **Trace data**: Netdata does not accept OTLP traces yet (as of skill-pack v0.1.0). Route traces elsewhere.
- **Log queries by free-form text**: Netdata's logs surface through the dashboard Logs tab and systemd journal queries. MCP does not yet expose a full-text log search tool.
- **Arbitrary SQL / code execution on the host**: `execute_function` is constrained to Netdata-registered functions. To run an arbitrary shell command, use SSH.
- **Write access to alert config**: alerts are managed via config files on the Netdata host.

## Transport choices (fast summary)

| Transport | Use when | Client support |
|---|---|---|
| HTTP streamable (`/mcp`) | Default. Remote agent connecting to Netdata over a network. | Recent Claude Code, Cursor. |
| SSE (`/mcp?transport=sse` or `/sse`) | Proxies or clients that prefer SSE. | Older Claude Code, some versions of Cursor. |
| WebSocket (`ws://…/mcp`) | Bidirectional streaming needs, or long-session connections. | Most clients. |
| stdio via `nd-mcp` | Clients that only speak stdio (Codex, Gemini CLI in stdio mode, Claude Desktop). | All the above, plus Claude Desktop. |

The Netdata side exposes all four on the same port (`19999` by default). Pick whichever the client supports natively.

## Auth

Bearer token. The Agent generates a UUID on first start and writes it to `/var/lib/netdata/mcp_dev_preview_api_key`. The token is static until the file is regenerated.

There is **no** per-tool permission scoping. A valid bearer gives access to every tool. If a client should not have `execute_function`, handle that at the client level (most clients confirm side-effecting tool calls with the user).

## Parent vs child vs Cloud

- A **Child / standalone** MCP sees that one node.
- A **Parent** MCP sees every child streaming to it (fleet view).
- **Netdata Cloud MCP** sees everything in the Cloud workspace (multi-parent view). Availability is rolling out; check the Netdata docs for current status.

Connect the agent to the highest-level view that is still safely reachable for the task. Asking a child "how is the fleet doing?" gets you a one-node answer.
