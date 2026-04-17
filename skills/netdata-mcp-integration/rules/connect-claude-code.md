# Connect Claude Code to Netdata MCP

## Two ways

- **Project-scoped**: put an `.mcp.json` file at the project root.
  Checked into the repo, shared by everyone on the project.
- **User-scoped**: use `claude mcp add ...`. Stored in the user's
  Claude Code config, not shared.

Pick project-scoped for team repos. Pick user-scoped for personal
machines and for connecting to your home-lab Parent.

## Read the API key off the Netdata host

```bash
# native package:
sudo cat /var/lib/netdata/mcp_dev_preview_api_key

# static install:
sudo cat /opt/netdata/var/lib/netdata/mcp_dev_preview_api_key
```

Copy the UUID. It rotates only if you delete the file.

## Project-scoped via `.mcp.json`

Create `.mcp.json` at the repo root:

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

Replace `YOUR_API_KEY` and `NETDATA_HOST`. Restart Claude Code.
Running `claude mcp list` should show `netdata` in the list.

## User-scoped via CLI

```bash
claude mcp add netdata /usr/bin/nd-mcp \
  --bearer YOUR_API_KEY \
  ws://NETDATA_HOST:19999/mcp
```

Same result, written to `~/.claude/mcp.json`.

## Native HTTP (no bridge)

Claude Code supports HTTP streamable directly, which removes the
`nd-mcp` dependency:

```json
{
  "mcpServers": {
    "netdata": {
      "url": "http://NETDATA_HOST:19999/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY",
        "Accept": "application/json"
      }
    }
  }
}
```

Use this form when the Claude Code version supports it (see
`claude --version`). It is faster and skips a process per session.

## Bridge binary paths

If `/usr/bin/nd-mcp` is not where Netdata installed:

| Install | Path |
|---|---|
| Native package (deb/rpm) | `/usr/bin/nd-mcp` or `/usr/sbin/nd-mcp` |
| Static install | `/opt/netdata/usr/bin/nd-mcp` |
| macOS from source | `/usr/local/netdata/usr/bin/nd-mcp` |
| Windows | `C:\Program Files\Netdata\usr\bin\nd-mcp.exe` |

## Troubleshooting

- **Tool list empty**: the bridge connected but authentication failed.
  Check the bearer token. The bridge prints errors to stderr, visible
  via `claude mcp list --verbose` on recent Claude Code versions.
- **`nd-mcp: command not found`**: Netdata is not installed on the
  client machine. Either install Netdata locally for `nd-mcp`, or use
  the native HTTP form above.
- **Connection to WS fails with timeout**: firewall between client and
  Netdata is blocking the WebSocket upgrade. Try the HTTP form which
  keeps the transport to plain request/response.
