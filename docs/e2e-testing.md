# End-to-end testing

How the v0.1 E2E harness works, what it proves, and how to extend it.

## Goal

Prove that the instrumentation patterns the skills teach actually work against a real Netdata instance. A skill whose code samples do not produce telemetry is worse than no skill; this harness stops such a skill from shipping.

## What runs

```
[ Docker ]                      [ host ]
+-------------------+            +----------------------+
|   Netdata (2.10)  |  :4317 <-- | sample app           |
|   otel.yaml       |            | (Node.js or Python)  |
|   /api/v2/contexts|            | instrumented with    |
|   /mcp            |            | OTel SDK             |
+-------------------+            +----------------------+
       ^                                  ^
       |                                  |
       |  [ verify-metrics.py ]            |
       |  MCP JSON-RPC probe               |
       |  REST fallback                    |
       |                                  |
       +----------- [ traffic.sh ] -------+
                     curl /hello 30s
```

## Layout

See [`../tests/e2e/README.md`](../tests/e2e/README.md) for the file-by-file map. Short version:

- `docker-compose.yml`: Netdata container with the OTLP receiver enabled.
- `netdata-config/otel.yaml`: minimal receiver config mounted into the container.
- `sample-apps/nodejs/` and `sample-apps/python/`: minimal services with OTel SDK instrumentation. Init code is byte-identical to the matching rule file.
- `traffic.sh`: curl loop.
- `verify-metrics.py`: MCP probe with REST fallback.
- `run-e2e.sh`: orchestrator.

## Host port overrides

On this build machine, ports 19999 and 8080 are in use. The harness uses remapped host ports:

- Netdata dashboard + MCP: `http://localhost:19998`
- OTLP gRPC: `localhost:4317` (unchanged)
- Sample app: `http://localhost:8088`

Skill rule files continue to document the standard 19999 / 4317 / 8080 defaults because that is what users see on clean machines. The overrides live only inside the harness.

## What the verifier checks

1. **MCP handshake**: `initialize` → `tools/list` must return ≥ 10 tools.
2. **MCP call**: `tools/call list_metrics` must return a response that mentions the sample app's `service.name`.
3. **REST fallback**: if MCP does not find the service name in the expected shape, fall back to `/api/v2/contexts` and accept any OTel-origin context (`otel.*` or `http.server.*`) as partial proof.

The fallback is marked `TODO: migrate to MCP` in code. A future release should tighten the MCP path so it passes without fallback.

## When it fails

See the troubleshooting section in [`../tests/e2e/README.md`](../tests/e2e/README.md).

Summarized:

| Symptom | Likely cause |
|---|---|
| Netdata web never comes up | Port collision, bad volume, Docker permissions. `docker compose logs netdata`. |
| OTLP port never opens | Plugin failed to load. `docker compose logs netdata \| grep otel`. |
| Sample app crashes on start | SDK version mismatch. Check `node_modules/@opentelemetry/*/package.json` vs rule file. |
| Traffic sent, metrics missing | Wrong exporter (HTTP vs gRPC), wrong endpoint, or fixture/rule drift. |
| MCP fails, REST succeeds | Known fallback path. Acceptable for v0.1; tracking as a follow-up. |

## Adding a language

1. Add `tests/e2e/sample-apps/<lang>/` with an `instrument.*` and a one-endpoint web app.
2. Copy the SDK init from the matching rule file (`skills/netdata-instrumentation/rules/<lang>.md`).
3. Add a branch in `run-e2e.sh` that installs deps and starts the service.
4. Run `bash tests/e2e/run-e2e.sh <lang>`.
5. If it fails, fix both the fixture and the rule. The fixture is the source of truth.

## CI integration

`.github/workflows/e2e.yml` runs `bash tests/e2e/run-e2e.sh nodejs` on every main-branch push and nightly. Python is on the stretch goal path; wire it similarly once Python fixture stability is proven across runners.

## What this is not

- **Load test**: this runs 30 seconds of trickle traffic. It does not prove Netdata's OTLP receiver scales to production rates.
- **Chaos test**: no Netdata restarts, no network partitions, no client retries exercised.
- **Dashboard test**: no verification of chart rendering or alert firing.

Those belong in a separate harness. v0.1 is scoped to "the pipeline from producer SDK to Netdata MCP works end to end". That is the ingress everything else depends on.
