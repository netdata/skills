# PHP instrumentation

## Approach

PHP has two paths: the PECL extension for automatic instrumentation
(requires compiling a C extension, works with most frameworks), or
manual SDK wiring in userland code. The PECL extension has much wider
library coverage; use it where possible.

## PECL extension path

```bash
pecl install opentelemetry
```

Add to `php.ini`:

```ini
extension=opentelemetry.so
```

Install the userland packages:

```bash
composer require \
  open-telemetry/sdk \
  open-telemetry/exporter-otlp \
  php-http/guzzle7-adapter \
  open-telemetry/opentelemetry-auto-symfony \
  open-telemetry/opentelemetry-auto-laravel
```

Pick the `auto-*` packages for the frameworks in use. OTLP/HTTP export
needs a PSR-18 HTTP client such as `php-http/guzzle7-adapter`
(opentelemetry.io PHP exporters page).

## Environment variables

```bash
export OTEL_PHP_AUTOLOAD_ENABLED=true
export OTEL_SERVICE_NAME=checkout
export OTEL_RESOURCE_ATTRIBUTES=service.version=1.4.0,deployment.environment=production
export OTEL_EXPORTER_OTLP_ENDPOINT=http://netdata.example.internal:4318
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_METRICS_EXPORTER=otlp
export OTEL_TRACES_EXPORTER=otlp   # "none" if the Agent has no trace receiver
export OTEL_LOGS_EXPORTER=none
```

With `OTEL_PHP_AUTOLOAD_ENABLED=true`, the auto-instrumentation hooks
register at Composer autoload time.

PHP's OTLP exporter defaults to `http/protobuf`. It sends to the Agent's
OTLP/HTTP listener, which must be on
(`receivers.otlp.protocols.http.enabled: true`; see the otel-setup
skill), and appends `/v1/metrics`, `/v1/traces`, or `/v1/logs` to the
endpoint. For gRPC on port 4317 instead, install the `grpc` extension and
`open-telemetry/transport-grpc`, then set
`OTEL_EXPORTER_OTLP_PROTOCOL=grpc` and the endpoint to port 4317.

## Manual SDK wiring

When the PECL extension cannot be installed:

```php
<?php
use OpenTelemetry\SDK\Metrics\MeterProvider;
use OpenTelemetry\SDK\Metrics\MetricReader\ExportingReader;
use OpenTelemetry\SDK\Resource\ResourceInfoFactory;
use OpenTelemetry\SDK\Resource\ResourceInfo;
use OpenTelemetry\Contrib\Otlp\MetricExporter;
use OpenTelemetry\Contrib\Otlp\OtlpHttpTransportFactory;
use OpenTelemetry\API\Common\Attribute\Attributes;

$transport = (new OtlpHttpTransportFactory())->create(
    getenv('OTEL_EXPORTER_OTLP_METRICS_ENDPOINT') ?: 'http://localhost:4318/v1/metrics',
    'application/x-protobuf'
);
$exporter = new MetricExporter($transport);
$reader   = new ExportingReader($exporter);

$resource = ResourceInfoFactory::defaultResource()->merge(
    ResourceInfo::create(Attributes::create([
        'service.name'           => getenv('OTEL_SERVICE_NAME') ?: 'checkout',
        'service.version'        => getenv('OTEL_SERVICE_VERSION') ?: '0.0.0',
        'deployment.environment' => getenv('DEPLOYMENT_ENV') ?: 'development',
    ]))
);

$meterProvider = MeterProvider::builder()
    ->setResource($resource)
    ->addReader($reader)
    ->build();

// keep a reference across the request lifecycle
$GLOBALS['__otel_meter_provider'] = $meterProvider;

register_shutdown_function(function () use ($meterProvider) {
    $meterProvider->shutdown();
});
```

The HTTP transport takes the full signal URL. For gRPC, the
`GrpcTransportFactory` from `open-telemetry/transport-grpc` takes the
gRPC method path instead
(`'http://localhost:4317' . OtlpUtil::method(Signals::METRICS)`).

## Traces

With the PECL extension and `OTEL_PHP_AUTOLOAD_ENABLED=true`,
`OTEL_TRACES_EXPORTER=otlp` sends spans to Netdata with the environment
above: OTLP/HTTP to `/v1/traces` on port 4318. The gRPC protocol (port
4317) needs the `open-telemetry/transport-grpc` Composer package and the
`grpc` PHP extension.

Use traces only when the Agent accepts them (nightly after 2026-08-17,
or the first stable release after v2.11.1). Otherwise keep
`OTEL_TRACES_EXPORTER=none`. Spans appear in the Traces tab under the
service name.

## Verification

```bash
curl -s 'http://NETDATA_HOST:19999/api/v2/contexts' \
  | jq --arg svc "$OTEL_SERVICE_NAME" \
       '.contexts | to_entries[] | select(.key | contains($svc))'
```

## Known limitation

PHP's per-request lifecycle makes metric readers awkward in traditional
mod_php + Apache / FPM setups. Each request spins up a fresh process
(or worker slot) and the PeriodicReader never gets a chance to batch.
For metrics specifically, prefer routing through an OTel Collector
running as a sidecar or node agent; see
`skills/netdata-collector-config/rules/daemonset-deployment.md`.
