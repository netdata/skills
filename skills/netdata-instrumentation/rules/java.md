# Java instrumentation

## Approach

Prefer the Java agent. It attaches at JVM start, patches the common
libraries, and exports metrics without code changes. Use manual SDK
wiring only when the agent cannot run (for example, on shrink-wrapped
app servers that forbid Java agents).

## Java agent path

Download the latest release jar:

```bash
curl -LO https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/latest/download/opentelemetry-javaagent.jar
```

Attach at JVM start:

```bash
java -javaagent:/opt/otel/opentelemetry-javaagent.jar \
     -Dotel.service.name=checkout \
     -Dotel.service.version=1.4.0 \
     -Dotel.resource.attributes=deployment.environment=production \
     -Dotel.exporter.otlp.endpoint=http://netdata.example.internal:4317 \
     -Dotel.exporter.otlp.protocol=grpc \
     -Dotel.metrics.exporter=otlp \
     -Dotel.traces.exporter=otlp \
     -Dotel.logs.exporter=none \
     -jar checkout.jar
```

System properties and the matching environment variables (below) are
equivalent; pick one style per deployment.

## Environment variables

```bash
export OTEL_SERVICE_NAME=checkout
export OTEL_SERVICE_VERSION=1.4.0
export OTEL_RESOURCE_ATTRIBUTES=deployment.environment=production
export OTEL_EXPORTER_OTLP_ENDPOINT=http://netdata.example.internal:4317
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_METRICS_EXPORTER=otlp
export OTEL_TRACES_EXPORTER=otlp
export OTEL_LOGS_EXPORTER=none
```

## Agent coverage

Out of the box the agent instruments Servlet containers (Tomcat,
Jetty, Undertow), Spring Web, Spring Boot, JDBC, Hibernate, HTTP
clients (Apache HttpClient, OkHttp, the JDK `HttpClient`), gRPC, Kafka
clients, JMS, Redis (Lettuce, Jedis), and many others. Each adds
matching metrics and spans.

## Manual SDK init (when the agent cannot run)

Dependencies (Gradle):

```groovy
implementation "io.opentelemetry:opentelemetry-api:1.44.0"
implementation "io.opentelemetry:opentelemetry-sdk:1.44.0"
implementation "io.opentelemetry:opentelemetry-exporter-otlp:1.44.0"
implementation "io.opentelemetry:opentelemetry-sdk-extension-autoconfigure:1.44.0"
```

Init in an application bootstrap class:

```java
OpenTelemetrySdk sdk = OpenTelemetrySdk.builder()
    .setMeterProvider(
        SdkMeterProvider.builder()
            .registerMetricReader(
                PeriodicMetricReader.builder(
                    OtlpGrpcMetricExporter.builder()
                        .setEndpoint("http://netdata.example.internal:4317")
                        .build()
                ).setInterval(Duration.ofSeconds(10)).build()
            )
            .setResource(
                Resource.getDefault().merge(Resource.builder()
                    .put("service.name", "checkout")
                    .put("service.version", "1.4.0")
                    .put("deployment.environment", "production")
                    .build())
            )
            .build()
    )
    .buildAndRegisterGlobal();
```

## Traces

With the agent, `otel.traces.exporter=otlp` and
`otel.exporter.otlp.protocol=grpc` send spans to Netdata on the same
endpoint as metrics. The agent's default protocol is `http/protobuf`, so
keep the protocol setting explicit for port 4317. With the Agent's
OTLP/HTTP listener on, the default works too: drop the protocol setting
and point `otel.exporter.otlp.endpoint` at port 4318.

When the Agent has no trace receiver (stable v2.11.x or older), set
`otel.traces.exporter=none` (or `OTEL_TRACES_EXPORTER=none`).

With manual SDK wiring, add a tracer provider to the builder above:

```java
.setTracerProvider(
    SdkTracerProvider.builder()
        .addSpanProcessor(
            BatchSpanProcessor.builder(
                OtlpGrpcSpanExporter.builder()
                    .setEndpoint("http://netdata.example.internal:4317")
                    .build()
            ).build()
        )
        .setResource(resource)
        .build()
)
```

`resource` is the `Resource` built inline for the meter provider above;
extract it to a local variable so both providers share it. Spans
appear in the Traces tab under the service name. See
`skills/netdata-otel-setup/rules/trace-ingestion.md` for the version
check.

## Shading pitfall

If the app already packages a different version of the OTel API, the
agent's patching can conflict. The agent's own copy of the API is
shaded; do not shadow it with a different version on the classpath.

## Verification

Use the MCP `list_metrics` tool with a `service.name: checkout`
attribute filter. Any `jvm.*`, `http.server.*`, or custom app metric
appearing confirms end-to-end ingestion.
