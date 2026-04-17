# Connect Cursor to Netdata MCP

## File to edit

Cursor reads MCP server configs from its settings. Add the Netdata
entry to your Cursor settings JSON (Settings → Cursor Settings → MCP).

## Stdio via `nd-mcp` bridge

```json
{
  "mcpServers": {
    "netdata": {
      "command": "/usr/bin/nd-mcp",
      "args": [
        "--bearer", "YOUR_API_KEY",
        "ws://NETDATA_HOST:19999/mcp"
      ]
    }
  }
}
```

Replace `YOUR_API_KEY` and `NETDATA_HOST`. The API key lives at
`/var/lib/netdata/mcp_dev_preview_api_key` on the Netdata host.

Restart Cursor. The Netdata tools should appear in the tool picker
after a few seconds.

## Native HTTP streamable

Recent Cursor versions speak HTTP streamable directly:

```json
{
  "mcpServers": {
    "netdata": {
      "url": "http://NETDATA_HOST:19999/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY"
      }
    }
  }
}
```

Prefer this form when available. It avoids the bridge process and its
dependency on a local Netdata install.

## SSE transport

Some Cursor versions prefer SSE. Use the `/sse` path (or append
`?transport=sse` to `/mcp`):

```json
{
  "mcpServers": {
    "netdata": {
      "url": "http://NETDATA_HOST:19999/mcp?transport=sse",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY"
      }
    }
  }
}
```

## Per-workspace override

To scope Netdata MCP to a single project, add a workspace-local
`mcp.json` under the project's `.cursor/` directory with the same
shape. Cursor merges workspace config over user config.

## Troubleshooting

- **Tools never appear**: Cursor silently retries failed MCP servers.
  Check the Cursor Output panel (View → Output → MCP) for JSON-RPC
  handshake errors.
- **"Unauthorized" from Netdata**: the bearer token is wrong, stale,
  or has a trailing whitespace from copy-paste. Re-copy:
  `sudo cat /var/lib/netdata/mcp_dev_preview_api_key | tr -d '\n'`.
- **Tools list populated but queries fail**: usually a child-node
  permissions issue. The Netdata instance you pointed at can only
  answer for nodes it actually sees. Reconnect to a Parent if the
  target is further up the tree.
