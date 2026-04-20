# .NET instrumentation

## Approach

Two options: the OpenTelemetry .NET Automatic Instrumentation (attaches
at process start, no code changes) or manual SDK wiring in
`Program.cs`. For ASP.NET Core services, manual wiring is common and
clean. For legacy .NET Framework, use the automatic installer.

## Automatic instrumentation

Install for the current process:

```bash
curl -L -o otel-dotnet-auto-install.sh \
  https://github.com/open-telemetry/opentelemetry-dotnet-instrumentation/releases/latest/download/otel-dotnet-auto-install.sh
sh otel-dotnet-auto-install.sh
. $HOME/.otel-dotnet-auto/instrument.sh
```

Then run the app with env vars set:

```bash
export OTEL_SERVICE_NAME=checkout
export OTEL_RESOURCE_ATTRIBUTES=service.version=1.4.0,deployment.environment=production
export OTEL_EXPORTER_OTLP_ENDPOINT=http://netdata.example.internal:4317
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_METRICS_EXPORTER=otlp
export OTEL_TRACES_EXPORTER=none
export OTEL_LOGS_EXPORTER=none
dotnet run
```

## Manual SDK wiring (ASP.NET Core)

NuGet packages:

```xml
<PackageReference Include="OpenTelemetry.Extensions.Hosting" Version="1.10.0" />
<PackageReference Include="OpenTelemetry.Exporter.OpenTelemetryProtocol" Version="1.10.0" />
<PackageReference Include="OpenTelemetry.Instrumentation.AspNetCore" Version="1.10.0" />
<PackageReference Include="OpenTelemetry.Instrumentation.Http" Version="1.10.0" />
<PackageReference Include="OpenTelemetry.Instrumentation.Runtime" Version="1.10.0" />
```

`Program.cs`:

```csharp
using OpenTelemetry;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddOpenTelemetry()
    .ConfigureResource(resource => resource
        .AddService(
            serviceName: Environment.GetEnvironmentVariable("OTEL_SERVICE_NAME") ?? "checkout",
            serviceVersion: "1.4.0")
        .AddAttributes(new Dictionary<string, object>
        {
            ["deployment.environment"] = Environment.GetEnvironmentVariable("DEPLOYMENT_ENV") ?? "development"
        }))
    .WithMetrics(metrics => metrics
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddRuntimeInstrumentation()
        .AddOtlpExporter(o =>
        {
            o.Endpoint = new Uri(
                Environment.GetEnvironmentVariable("OTEL_EXPORTER_OTLP_ENDPOINT") ?? "http://localhost:4317");
            o.Protocol = OpenTelemetry.Exporter.OtlpExportProtocol.Grpc;
        }));

var app = builder.Build();
app.MapGet("/hello", () => new { ok = true });
app.Run();
```

## Traces

Netdata does not accept traces yet. Either omit `.WithTracing(...)`
entirely, or register traces with a different exporter pointed at a
real trace backend.

## Legacy .NET Framework

Use `OpenTelemetry.Extensions.Hosting` only on .NET 6+. On classic
.NET Framework, instantiate the `MeterProvider` directly via
`Sdk.CreateMeterProviderBuilder()` and keep a reference for the
process lifetime.

## Verification

```bash
curl -s 'http://NETDATA_HOST:19999/api/v2/contexts' | jq '.contexts | keys[]' | grep checkout
```

`process.runtime.dotnet.*` metrics from `AddRuntimeInstrumentation()`
confirm end-to-end ingestion independently of any app-specific metric.
