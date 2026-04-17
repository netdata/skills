# Go instrumentation

## Approach

Go does not have a drop-in Java-style agent, though the
[otel-go-auto-instrumentation](https://github.com/open-telemetry/opentelemetry-go-instrumentation)
eBPF project is progressing. For production today, wire the SDK in
code. Use `go.opentelemetry.io/contrib/instrumentation/...` packages
to wrap individual libraries.

## Dependencies

```bash
go get \
  go.opentelemetry.io/otel \
  go.opentelemetry.io/otel/sdk \
  go.opentelemetry.io/otel/sdk/metric \
  go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc \
  go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp
```

## Minimal SDK init

```go
package main

import (
    "context"
    "log"
    "os"
    "time"

    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
    sdkmetric "go.opentelemetry.io/otel/sdk/metric"
    "go.opentelemetry.io/otel/sdk/resource"
    semconv "go.opentelemetry.io/otel/semconv/v1.26.0"
)

func initMeterProvider(ctx context.Context) (*sdkmetric.MeterProvider, error) {
    endpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint == "" {
        endpoint = "localhost:4317"
    }

    exporter, err := otlpmetricgrpc.New(ctx,
        otlpmetricgrpc.WithEndpoint(endpoint),
        otlpmetricgrpc.WithInsecure(),
    )
    if err != nil {
        return nil, err
    }

    res, err := resource.New(ctx,
        resource.WithAttributes(
            semconv.ServiceName(getenv("OTEL_SERVICE_NAME", "unnamed-service")),
            semconv.ServiceVersion(getenv("OTEL_SERVICE_VERSION", "0.0.0")),
            semconv.DeploymentEnvironment(getenv("DEPLOYMENT_ENV", "development")),
        ),
    )
    if err != nil {
        return nil, err
    }

    mp := sdkmetric.NewMeterProvider(
        sdkmetric.WithResource(res),
        sdkmetric.WithReader(
            sdkmetric.NewPeriodicReader(exporter,
                sdkmetric.WithInterval(5*time.Second),
            ),
        ),
    )
    otel.SetMeterProvider(mp)
    return mp, nil
}

func getenv(k, d string) string {
    if v := os.Getenv(k); v != "" {
        return v
    }
    return d
}

func main() {
    ctx := context.Background()
    mp, err := initMeterProvider(ctx)
    if err != nil {
        log.Fatal(err)
    }
    defer func() {
        ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
        defer cancel()
        _ = mp.Shutdown(ctx)
    }()

    // app starts here
}
```

## Note on endpoint format

The Go gRPC exporter takes the endpoint without a scheme prefix
(`localhost:4317`). Many SDKs accept both forms; Go's is strict. If you
want to reuse the same `OTEL_EXPORTER_OTLP_ENDPOINT` value across
languages, strip the scheme in Go:

```go
endpoint = strings.TrimPrefix(endpoint, "http://")
endpoint = strings.TrimPrefix(endpoint, "https://")
```

## Wrapping HTTP handlers

```go
import (
    "net/http"
    "go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
)

http.Handle("/hello", otelhttp.NewHandler(
    http.HandlerFunc(helloHandler),
    "hello",
))
```

`otelhttp` records span data (not exported to Netdata yet) and HTTP
server metrics (exported).

## Traces

Netdata does not accept traces yet. Do not register a
`WithBatcher(OTLPTraceExporter)` pointed at Netdata. If the app needs
tracing in parallel, register a separate trace exporter against a trace
backend.

## Verification

Send traffic and query:

```bash
curl -s 'http://NETDATA_HOST:19999/api/v2/contexts' \
  | jq --arg svc "$OTEL_SERVICE_NAME" \
       '.contexts | to_entries[] | select(.key | contains($svc))'
```
