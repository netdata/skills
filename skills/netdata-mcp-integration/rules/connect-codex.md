# Connect Codex (OpenAI) and Gemini CLI to Netdata MCP

## Codex

Codex reads MCP server config from `~/.codex/config.toml` (or
project-scoped `.codex/config.toml` in a trusted project). Each MCP
server is registered as a `[mcp_servers.<name>]` table. Codex
supports two server shapes: stdio (via a local bridge command) and
HTTP (direct to a remote MCP endpoint).

### HTTP server (preferred for Netdata)

Netdata's MCP endpoint speaks HTTP streamable on both local Agents
(v2.7.2+) and Netdata Cloud. Point Codex directly at it:

```toml
# ~/.codex/config.toml — local Agent or Parent
[mcp_servers.netdata]
url = "http://NETDATA_HOST:19999/mcp"
bearer_token_env_var = "NETDATA_MCP_TOKEN"
```

```toml
# ~/.codex/config.toml — Netdata Cloud
[mcp_servers.netdata-cloud]
url = "https://app.netdata.cloud/api/v1/mcp"
bearer_token_env_var = "NETDATA_CLOUD_API_TOKEN"
```

Export the matching env var in the shell Codex runs in:

```bash
export NETDATA_MCP_TOKEN="$(ssh NETDATA_HOST sudo cat /var/lib/netdata/mcp_dev_preview_api_key)"
# or, for Cloud:
export NETDATA_CLOUD_API_TOKEN="<token from Cloud UI>"
```

### stdio server (for older Agents or WebSocket)

If the target Agent is older than v2.7.2, HTTP streamable is not
available; connect via the `nd-mcp` bridge over WebSocket instead:

```toml
# ~/.codex/config.toml
[mcp_servers.netdata]
command = "/usr/bin/nd-mcp"
args = ["ws://NETDATA_HOST:19999/mcp"]

[mcp_servers.netdata.env]
ND_MCP_BEARER = "paste-token-here"
```

WebSocket is available on Netdata v2.6.0+. Pass the token through an
env var the bridge reads, not as a CLI flag.

Restart Codex, then run `/mcp` (or the equivalent in your Codex
version) to confirm the `netdata` server is listed with its tools.

## Gemini CLI

Gemini CLI reads MCP config from either `~/.gemini/settings.json` or
per-project `.gemini/settings.json`.

```json
{
  "mcpServers": {
    "netdata": {
      "command": "/usr/bin/nd-mcp",
      "args": ["ws://NETDATA_HOST:19999/mcp"],
      "env": { "ND_MCP_BEARER": "paste-token-here" }
    }
  }
}
```

For direct HTTP streamable against v2.7.2+ Agents or Cloud, use the
HTTP form Gemini CLI supports in its current release; consult the
Gemini CLI docs for the exact JSON shape.

Launch Gemini CLI and type `/mcp` to list registered servers.

## Transport preferences

- For local Agents on v2.7.2 or newer, prefer HTTP streamable. It is
  stateless and proxy-friendly.
- For Agents between v2.6.0 and v2.7.1, use WebSocket through the
  `nd-mcp` bridge.
- For Netdata Cloud, only HTTP streamable is available; point Codex
  directly at the Cloud endpoint.
- stdio-via-bridge works against any of the above by URL scheme and
  is the most portable option when client HTTP support is uneven.

## API key rotation

If the token in `mcp_dev_preview_api_key` is rotated on the Netdata
host (by deleting the file and restarting Netdata), every client
config needs to be updated. There is no JWT expiry; the bearer value
is static until the file is regenerated.

For Cloud tokens, rotation happens in the Cloud UI; old tokens stop
working immediately after revocation.

## Troubleshooting

- **`nd-mcp` not in PATH**: hard-code the absolute path (see the
  Claude Code rule for path-per-platform table).
- **Tools appear but all calls time out**: the Netdata side is
  streaming a huge response or the agent's client-side MCP timeout is
  set too low. Raise the timeout in the client, or narrow the query.
- **`execute_function` is blocked**: Codex and Gemini CLI confirm
  side-effecting tools with the user by default. That is correct
  behavior; `execute_function` is the only MCP tool Netdata marks as
  having side effects.
- **HTTP form returns 404 on a local Agent**: the Agent is older
  than v2.7.2. Fall back to the WebSocket form via `nd-mcp`.

## Verify the connection

After restarting the client, run a probe prompt:

```text
Using the netdata MCP server, call list_nodes. Return the names
of the nodes visible.
```

A non-empty node list confirms the connection is alive and the
bearer token is accepted. An empty list with no error usually
means the Netdata instance you connected to is a standalone node
(which only sees itself).
