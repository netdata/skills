# Ruby instrumentation

## Install

```bash
gem install opentelemetry-sdk \
            opentelemetry-exporter-otlp-metrics \
            opentelemetry-instrumentation-all
```

The `opentelemetry-instrumentation-all` gem pulls in instrumentations
for common libraries (Net::HTTP, Rack, Rails, Sinatra, ActiveRecord,
Sidekiq, Faraday, Redis, and more). Pick per-library gems instead if
bundle size matters.

## Minimal SDK init

Put this in `config/opentelemetry.rb` (Rails) or at the top of the
main entry point:

```ruby
require "opentelemetry/sdk"
require "opentelemetry/exporter/otlp/metrics"
require "opentelemetry/instrumentation/all"

OpenTelemetry::SDK.configure do |c|
  c.service_name    = ENV.fetch("OTEL_SERVICE_NAME", "checkout")
  c.service_version = ENV.fetch("OTEL_SERVICE_VERSION", "0.0.0")
  c.resource        = OpenTelemetry::SDK::Resources::Resource.create(
    "deployment.environment" => ENV.fetch("DEPLOYMENT_ENV", "development")
  )
  c.use_all
end

# OTLP/HTTP: reads OTEL_EXPORTER_OTLP_ENDPOINT and appends /v1/metrics.
exporter = OpenTelemetry::Exporter::OTLP::Metrics::MetricsExporter.new(
  compression: "gzip"
)

reader = OpenTelemetry::SDK::Metrics::Export::PeriodicMetricReader.new(
  exporter: exporter,
  export_interval_millis: 5_000
)

OpenTelemetry.meter_provider.add_metric_reader(reader)
```

The Ruby OTLP metrics exporter speaks OTLP/HTTP only, so the Agent's
OTLP/HTTP listener must be on
(`receivers.otlp.protocols.http.enabled: true`; see the otel-setup
skill). An explicit `endpoint:` argument is used as-is, so it must carry
the full `/v1/metrics` URL. Source: `exporter/otlp-metrics` and
`exporter/otlp-common` in `opentelemetry-ruby`.

If the Agent has no OTLP/HTTP listener (receiver-format check in the
otel-setup skill), Ruby has no gRPC metrics exporter: send metrics
through an OTel Collector that exports gRPC to port 4317, and send
traces with the gRPC exporter below.

## Environment variables

```bash
export OTEL_SERVICE_NAME=checkout
export OTEL_SERVICE_VERSION=1.4.0
export DEPLOYMENT_ENV=production
export OTEL_EXPORTER_OTLP_ENDPOINT=http://netdata.example.internal:4318
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
```

## Rails integration

Require the config file from `config/application.rb` before Rails
loads:

```ruby
# config/application.rb (top of file)
require_relative "opentelemetry"
```

The `opentelemetry-instrumentation-rails` gem wires spans and metrics
for controller actions and DB queries.

## Sidekiq notes

Sidekiq workers load Rails after the process starts. If metrics are
missing from workers, confirm `config/opentelemetry.rb` runs in the
worker process, not just the web process. The simplest fix is
`require_relative` inside the worker's boot file as well.

## Traces

Ruby's default OTLP trace exporter (`opentelemetry-exporter-otlp`, used
when `OTEL_TRACES_EXPORTER=otlp`) speaks OTLP/HTTP. With the Agent's
OTLP/HTTP listener on, it sends spans to Netdata directly: install the
gem, require it before `OpenTelemetry::SDK.configure`, and keep the
environment above. The exporter posts to `/v1/traces` on port 4318.

```bash
gem install opentelemetry-exporter-otlp
```

```ruby
require "opentelemetry/exporter/otlp"
```

The SDK builds this exporter only for `http/protobuf`. With
`OTEL_EXPORTER_OTLP_PROTOCOL=grpc` it logs a warning and exports no spans
(`sdk/lib/opentelemetry/sdk/configurator.rb` in `opentelemetry-ruby`).
To send spans over gRPC to port 4317 instead, add the gRPC exporter gem
explicitly. A span processor added this way replaces the one built from
the environment.

```bash
gem install opentelemetry-exporter-otlp-grpc
```

```ruby
require "opentelemetry/exporter/otlp/grpc"

OpenTelemetry::SDK.configure do |c|
  # ...service_name, resource, use_all as above...
  c.add_span_processor(
    OpenTelemetry::SDK::Trace::Export::BatchSpanProcessor.new(
      OpenTelemetry::Exporter::OTLP::GRPC::TraceExporter.new(
        endpoint: ENV.fetch("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://localhost:4317")
      )
    )
  )
end
```

Source: `exporter/otlp/README.md` and `exporter/otlp-grpc/README.md` in
`opentelemetry-ruby`. Send traces only when the Agent accepts them
(nightly after 2026-08-17, or the first stable release after v2.11.1).
Otherwise set `OTEL_TRACES_EXPORTER=none` so the SDK does not start a
trace exporter. Spans appear in the Traces tab under the service name.

## Verification

```bash
curl -s 'http://NETDATA_HOST:19999/api/v2/contexts' \
  | jq --arg svc "$OTEL_SERVICE_NAME" \
       '.contexts | to_entries[] | select(.key | contains($svc))'
```
