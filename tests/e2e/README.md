# End-to-end test harness

This harness proves that the instrumentation patterns the skills teach
actually work against a real Netdata instance.

## What it does

1. Starts Netdata in Docker with OTLP/gRPC enabled on port 4317.
2. Builds and runs an instrumented Node.js or Python sample app on the
   host.
3. Generates traffic against the sample app for 30 seconds.
4. Queries Netdata (via MCP, falling back to REST) to confirm the
   sample app's metrics arrived.

Exit code 0 means the full pipeline works. Non-zero means something in
the skill-taught pattern is broken and a user following the skill would
not see their metrics.

## Host port overrides

This repo's build machine has ports 19999 and 8080 in use. The harness
uses the following host ports, remapped from the usual defaults:

- Netdata dashboard and MCP: `http://localhost:19998` (container internal
  still uses 19999).
- OTLP gRPC: `localhost:4317` (no remap; 4317 is free).
- Sample app: `http://localhost:8088` (the app listens on whatever
  `PORT` env var it receives).

**Skill content continues to document the standard defaults (19999 and
8080)** because those are what users see on clean machines. The overrides
are only used inside this harness.

## Prerequisites

- `docker` and `docker compose`
- `node` >= 20 and `npm`
- `python` >= 3.10 and `pip`
- `nc`, `curl`, `jq`
- ports 19998, 4317, 8088 free on the host

## Run it

```bash
bash tests/e2e/run-e2e.sh nodejs
# or
bash tests/e2e/run-e2e.sh python
```

Add a second argument to also verify the metric arrived in Netdata
Cloud:

```bash
bash tests/e2e/run-e2e.sh nodejs cloud
```

Cloud mode requires three environment variables:

- `NETDATA_CLAIM_TOKEN`     claim token from the target Cloud space
- `NETDATA_CLAIM_ROOMS`     comma-separated room IDs
- `NETDATA_CLOUD_API_TOKEN` bearer token for the Cloud MCP probe

Optional: `NETDATA_CLAIM_URL` (default `https://app.netdata.cloud`)
and `NETDATA_CLOUD_MCP_URL` (default
`https://app.netdata.cloud/api/v1/mcp`).

The Cloud probe pauses 45 seconds after local verification to let
the Agent stream + Cloud aggregate, then queries the Cloud MCP with
the same `list_metrics q-filter` pattern used locally.

The script is trap-safe: it stops the sample app and tears down the
Docker container on exit, even on failure.

## Verification path

`verify-metrics.py` prefers MCP:

1. `docker exec` into the Netdata container to read the bearer token
   from `/var/lib/netdata/mcp_dev_preview_api_key`.
2. Call `initialize` → `tools/list` → `tools/call list_metrics` via
   HTTP-streamable JSON-RPC at `http://localhost:19998/mcp`.
3. Invoke `list_metrics` with `{"metrics": "*", "nodes": "*", "q": <service-name>}`.
   Netdata enters SEARCH mode when `q` is set and includes labels,
   instances, and dimensions in the response (see
   `_reference/netdata/src/web/mcp/mcp-tools-list-metadata.c:503-506`).
   The OTel `service.name` attribute rides through as an instance
   label.
4. Parse the JSON-encoded `result.content[0].text` payload and count
   matched contexts. Any non-zero count confirms metadata matching
   the service name exists on the Netdata side.

If the MCP path fails (connection error, unparsable payload, zero
matches), the script falls back to Netdata's REST `/api/v2/contexts`.
REST is the safety net so transient MCP quirks do not gate the
release, but the MCP path is what the skill teaches and what CI
should report on.

## Layout

```
tests/e2e/
├── README.md                 # you are here
├── docker-compose.yml        # Netdata container definition
├── netdata-config/otel.yaml  # minimal OTLP receiver config
├── sample-apps/
│   ├── nodejs/
│   │   ├── package.json
│   │   ├── instrument.js     # must match skills/netdata-instrumentation/rules/nodejs.md
│   │   └── index.js          # minimal Express /hello handler
│   └── python/
│       ├── requirements.txt
│       ├── instrument.py     # must match skills/netdata-instrumentation/rules/python.md
│       └── app.py            # minimal Flask /hello handler
├── traffic.sh                # curl loop
├── verify-metrics.py         # local Agent MCP + REST probe
├── verify-metrics-cloud.py   # Netdata Cloud MCP probe (cloud mode)
├── run-e2e.sh                # orchestrator
└── .gitignore                # node_modules, .venv, etc.
```

## Byte-for-byte contract

The SDK init code in `sample-apps/nodejs/instrument.js` and
`sample-apps/python/instrument.py` must match the code block in the
matching rule file (`skills/netdata-instrumentation/rules/nodejs.md`,
`rules/python.md`) byte for byte. The fixture is the source of truth:
if the fixture runs green, the skill teaches a working pattern. A PR
that edits one must edit the other in the same commit.

## Extending to new languages

1. Add `sample-apps/<lang>/` with the same shape (SDK init + simple
   web handler).
2. Add a branch in `run-e2e.sh` that installs deps and starts the
   service.
3. Run the harness. If it fails, fix the SDK init in both the fixture
   and the matching rule file.

## When it fails

Typical failure modes:

- **Netdata web never comes up**: `docker compose logs netdata` has the
  answer. Usually a port collision or an unreadable volume mount.
- **OTLP port never opens**: the plugin failed to load. Look for
  `otel-plugin` lines in `docker compose logs netdata`.
- **Sample app connects but no metrics appear**: usually the app's
  `OTEL_EXPORTER_OTLP_ENDPOINT` is wrong, or it is using the HTTP
  exporter by accident. Verify the fixture uses
  `@opentelemetry/exporter-metrics-otlp-grpc` (Node.js) or
  `opentelemetry.exporter.otlp.proto.grpc` (Python).
- **MCP handshake fails**: check the bearer token via
  `docker exec netdata-skills-e2e cat /var/lib/netdata/mcp_dev_preview_api_key`.
