# Node.js instrumentation

## Install

```bash
npm install \
  @opentelemetry/api \
  @opentelemetry/sdk-node \
  @opentelemetry/sdk-metrics \
  @opentelemetry/exporter-metrics-otlp-grpc \
  @opentelemetry/auto-instrumentations-node
```

## Minimal SDK init

Save as `instrument.js` at the service root. Load it before the app starts
(below). Resource attributes come from env vars, which the SDK picks up
automatically; that keeps the code free of version-sensitive Resource API
calls.

```javascript
// instrument.js
const { NodeSDK } = require('@opentelemetry/sdk-node');
const { OTLPMetricExporter } = require('@opentelemetry/exporter-metrics-otlp-grpc');
const { PeriodicExportingMetricReader } = require('@opentelemetry/sdk-metrics');
const { getNodeAutoInstrumentations } = require('@opentelemetry/auto-instrumentations-node');

const endpoint = process.env.OTEL_EXPORTER_OTLP_ENDPOINT || 'http://localhost:4317';

const sdk = new NodeSDK({
  metricReader: new PeriodicExportingMetricReader({
    exporter: new OTLPMetricExporter({ url: endpoint }),
    exportIntervalMillis: 5000,
  }),
  instrumentations: [getNodeAutoInstrumentations()],
});

sdk.start();

process.on('SIGTERM', () => {
  sdk.shutdown().finally(() => process.exit(0));
});
```

Load it via `--require` so instrumentation patches happen before
application modules import their dependencies:

```bash
node --require ./instrument.js ./index.js
```

Or inside `package.json`:

```json
{
  "scripts": {
    "start": "node --require ./instrument.js ./index.js"
  }
}
```

## Required environment variables

```bash
export OTEL_SERVICE_NAME=checkout
export OTEL_RESOURCE_ATTRIBUTES=service.version=1.4.0,deployment.environment=production
export OTEL_EXPORTER_OTLP_ENDPOINT=http://netdata.example.internal:4317
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_TRACES_EXPORTER=otlp   # "none" if the Agent has no trace receiver
```

`OTEL_SERVICE_NAME` and `OTEL_RESOURCE_ATTRIBUTES` are picked up by the
default resource detector; there is no need to set them on the SDK in
code.

The gRPC exporter expects a bare `http://host:port` or `https://host:port`.

**Incorrect** (suffixes an HTTP path onto a gRPC endpoint, connection fails silently or returns 404):

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://netdata.example.internal:4317/v1/metrics
```

**Correct** (bare host:port for gRPC; `/v1/metrics` is the OTLP/HTTP path and belongs on a different exporter):

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://netdata.example.internal:4317
```

## Auto-instrumentation coverage

`@opentelemetry/auto-instrumentations-node` turns on the
instrumentation packages for most common libraries, including `http`,
`express`, `fastify`, `koa`, `mongodb`, `redis`, `pg`, `mysql2`,
`@aws-sdk/*`, and `grpc-js`. Each produces spans (exported to Netdata
when the Agent accepts traces) and a small set of metrics.

If the bundle is too heavy, cherry-pick individual instrumentations
instead:

```bash
npm install @opentelemetry/instrumentation-http @opentelemetry/instrumentation-express
```

```javascript
const { HttpInstrumentation } = require('@opentelemetry/instrumentation-http');
const { ExpressInstrumentation } = require('@opentelemetry/instrumentation-express');

// replace the instrumentations line:
instrumentations: [new HttpInstrumentation(), new ExpressInstrumentation()],
```

## Traces

The init above passes no `traceExporter`, so `NodeSDK` builds the trace
exporter from the environment (`@opentelemetry/sdk-node` README,
"Configure Exporters from environment"). Its default protocol is
`http/protobuf`; `OTEL_EXPORTER_OTLP_PROTOCOL=grpc` switches spans to
gRPC on the same endpoint as metrics.

- Agent accepts traces (nightly after 2026-08-17, or the first stable
  release after v2.11.1): keep `OTEL_TRACES_EXPORTER=otlp`. Spans appear
  in the Traces tab under the service name.
- Agent does not accept traces (stable v2.11.x or older): set
  `OTEL_TRACES_EXPORTER=none`, or point a separate trace exporter at the
  current trace backend.

See `skills/netdata-otel-setup/rules/trace-ingestion.md` for the version
check.

## Logs

The Node.js OTel logs SDK is still marked unstable at the time of this
skill's release. The preferred path for Node.js is to ship structured
logs via Pino or Winston to stdout, then have the OTel Collector's
`filelog` receiver pick them up and forward to Netdata. See
`skills/netdata-collector-config/rules/receivers.md`.

## Verification

With the agent that has MCP access to your Netdata:

```text
Call list_metrics with the "service.name" attribute filter set to
"checkout" and confirm at least one http.server.* metric is present.
```

See `skills/netdata-mcp-integration/` for the full query pattern.

## Worked example

The canonical runnable version of this pattern lives at
[`tests/e2e/sample-apps/nodejs/`](../../../tests/e2e/sample-apps/nodejs/).
The `instrument.js` there matches the code block above byte for byte;
if you change one, change the other in the same PR.
