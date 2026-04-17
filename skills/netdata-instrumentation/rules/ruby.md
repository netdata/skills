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

exporter = OpenTelemetry::Exporter::OTLP::Metrics::MetricsExporter.new(
  endpoint: ENV.fetch("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
  compression: "gzip"
)

reader = OpenTelemetry::SDK::Metrics::Export::PeriodicMetricReader.new(
  exporter: exporter,
  export_interval_millis: 5_000
)

OpenTelemetry.meter_provider.add_metric_reader(reader)
```

## Environment variables

```bash
export OTEL_SERVICE_NAME=checkout
export OTEL_SERVICE_VERSION=1.4.0
export DEPLOYMENT_ENV=production
export OTEL_EXPORTER_OTLP_ENDPOINT=http://netdata.example.internal:4317
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
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

Netdata does not accept traces yet. Ruby's OTel SDK configures the
trace exporter via the same env vars; set `OTEL_TRACES_EXPORTER=none`
to avoid pointing a trace stream at Netdata.

## Verification

```bash
curl -s 'http://NETDATA_HOST:19999/api/v2/contexts' \
  | jq --arg svc "$OTEL_SERVICE_NAME" \
       '.contexts | to_entries[] | select(.key | contains($svc))'
```
