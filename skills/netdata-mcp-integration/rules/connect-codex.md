# Connect Codex (OpenAI) and Gemini CLI to Netdata MCP

## Codex

OpenAI Codex supports MCP via its config file. Add a server entry:

```toml
# ~/.config/codex/config.toml
[[mcp_servers]]
name = "netdata"
command = "/usr/bin/nd-mcp"
args = ["--bearer", "YOUR_API_KEY", "ws://NETDATA_HOST:19999/mcp"]
```

For Codex versions that take JSON:

```json
{
  "mcpServers": {
    "netdata": {
      "command": "/usr/bin/nd-mcp",
      "args": ["--bearer", "YOUR_API_KEY", "ws://NETDATA_HOST:19999/mcp"]
    }
  }
}
```

Replace `YOUR_API_KEY` and `NETDATA_HOST` as in the other clients.
Restart Codex, then ask it to list its available MCP tools.

## Gemini CLI

Gemini CLI reads MCP config from either `~/.gemini/settings.json` or
per-project `.gemini/settings.json`.

```json
{
  "mcpServers": {
    "netdata": {
      "command": "/usr/bin/nd-mcp",
      "args": ["--bearer", "YOUR_API_KEY", "ws://NETDATA_HOST:19999/mcp"]
    }
  }
}
```

Launch Gemini CLI and type `/mcp` to list registered servers.

## Transport preferences

- Codex and Gemini CLI both speak stdio well via `nd-mcp`.
- For long-running sessions on remote Netdata, prefer the WebSocket
  URL (`ws://…`) as shown. It avoids polling and keeps the token
  handshake once per session.
- Native HTTP streamable works only on the newest builds of these
  clients; fall back to stdio-via-bridge when the HTTP form is
  unsupported.

## API key rotation

If the token in `mcp_dev_preview_api_key` is rotated on the Netdata
host (by deleting the file and restarting Netdata), every client
config needs to be updated. There is no JWT expiry; the bearer value
is static until the file is regenerated.

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
