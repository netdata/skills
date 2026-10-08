# Extract requirements

## Scope

How to turn a customer's written document into a structured requirement
inventory. The inventory drives every other decision in the bundle.

## The eight categories

Every bundle pass extracts values into these categories. Anything
missing becomes an open question.

### 1. Stack inventory

What the customer runs. The agent must record each item the customer
wants Netdata to see, even if the document mentions it in passing.

- Application languages and frameworks (Node.js, Python, Java, Go,
  .NET, Ruby, PHP, others).
- Databases and queues (PostgreSQL, MySQL, Redis, Kafka, Cassandra,
  RabbitMQ).
- Proxies and ingress (NGINX, HAProxy, Envoy, Traefik).
- Container platform (Docker, Kubernetes distribution, ECS, Nomad).
- Existing observability tooling (Datadog, New Relic, Dynatrace,
  Prometheus, Grafana, Tempo, Jaeger).
- Signals in scope: metrics, logs, traces. Traces need a Netdata Agent
  built after 2026-08-17 (nightly) or the first stable release after
  v2.11.1. Record the Agent version (or whether the customer can run
  nightly builds) next to any trace requirement.

### 2. Volume estimates

How much telemetry the customer expects.

- Metric rate per host or per cluster (data points per second).
- Log and span volume per day, if logs or traces are in scope. It sizes
  `logs.retention` and `traces.retention` (stock: 1GB or 7 days).
- Number of services in scope.
- Peak vs average request rate if mentioned.
- Cardinality hotspots the customer already knows about (for example
  `user_id` labels on HTTP metrics).

Missing volume estimates are common. Record them as open questions with
concrete options, not as "TBD." Example: "Expected metric rate per
host? Default assumption for sizing: 10k DPM. Customer to confirm."

### 3. Network topology

How telemetry flows from producers to Netdata.

- Single Netdata Agent, parent-child replication, or Netdata Cloud
  ingest?
- On-prem, cloud, or hybrid? Which cloud, which region?
- Firewall boundaries between producers and Netdata.
- NAT or proxy hops in the path.

### 4. Security posture

The TLS, auth, and isolation constraints.

- TLS on the OTLP receiver: required, optional, or off?
- Certificate source: public CA, private CA, cert-manager,
  self-signed?
- MTLS (client certificates required from producers)?
- Bearer token or other header auth on MCP or the dashboard?
- Network isolation: public endpoint, VPN-only, private link?

The Netdata OTLP receiver's TLS options live in
[`netdata-otel-setup/rules/tls-and-auth.md`](../../netdata-otel-setup/rules/tls-and-auth.md).
Cite the specific knobs in the bundle's `otel.yaml` comments, not the
prose.

### 5. Compliance constraints

Regulatory or internal policy drivers that shape what data can be sent
where.

- PII fields that must not leave the producer (affects attribute
  allowlists on the Collector).
- Regions that telemetry must stay within (affects Cloud endpoint
  choice).
- Audit logging requirements (who accessed what dashboard).
- Data retention floors and ceilings.

### 6. Deployment pattern

How the customer will install the Collector, if any.

- DaemonSet on each Kubernetes node.
- Gateway (one or a few central Collectors aggregating producers).
- OpenTelemetry Operator managing Collectors and auto-instrumentation.
- Sidecar per pod (uncommon, flag for clarification).
- No Collector, direct OTLP from producers to Netdata.

The decision belongs to `netdata-collector-config`; this skill only
records which pattern the customer chose and flags when the document
is silent.

### 7. Acceptance criteria

What "done" looks like for the customer. Extract verbatim.

- Specific metrics the customer expects to see (for example "request
  rate per service in the dashboard").
- SLA for telemetry freshness (for example "metrics must be visible
  within 30 seconds").
- Alerting expectations (for example "page on error rate above 1%").
- Retention expectations.

### 8. Timeline and phasing

Rollout constraints.

- Hard deadlines (regulatory, migration cutover).
- Phase 1 / phase 2 / phase N splits if the document sequences the
  work.
- Freeze windows (for example "no infra changes between Dec 20 and
  Jan 5").

## Extraction workflow

**Incorrect** (read partial, start writing, discover gaps late):

```text
1. Read the first two pages.
2. Start writing otel.yaml.
3. Realize page 7 contradicts page 2.
4. Rewrite.
```

**Correct** (full read, then inventory, then bundle):

```text
1. Read the whole document.
2. Fill in the eight categories above. Empty slots become open
   questions.
3. Decide sibling skill composition based on the filled inventory.
4. Emit the bundle.
```

## Ambiguity flagging

Every gap becomes a row in `open-questions.md` with three fields:

- **Question**: one sentence, phrased so the customer can answer it.
- **Why it matters**: the bundle decision blocked by this.
- **Assumed default**: what the bundle used while waiting. "Commented
  out" is a valid default; "inferred from context" is not.

**Incorrect** (silent default with no visibility):

```yaml
# otel.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: "0.0.0.0:4317"
        tls:
          cert_file: "/etc/netdata/tls/cert.pem"  # assumed TLS on
```

**Correct** (explicit pointer to the open question):

```yaml
# otel.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: "0.0.0.0:4317"
        # TLS: customer did not specify. See open-questions.md Q-03.
        # Defaulting to TLS off; uncomment and provide cert paths when
        # Q-03 is answered.
        # tls:
        #   cert_file: "/etc/netdata/tls/cert.pem"
        #   key_file: "/etc/netdata/tls/key.pem"
```

## Document-format handling

- **Plain prose / email**: parse linearly, populate categories.
- **Markdown**: respect existing section headers as hints for
  categories but do not trust them to be complete.
- **PDF or DOCX**: ask the user to paste relevant sections or convert
  to text. Do not fabricate values from filename or metadata alone.
- **Architecture diagrams (image)**: ask the user to describe each
  labeled node in text before proceeding. Images without text
  descriptions are insufficient for a production bundle.

## What the inventory is not

- Not a design document. Do not write rationale for each extracted
  value.
- Not a parroting of the customer's prose. Each value is atomic and
  answerable.
- Not exhaustive beyond the eight categories. Extra context lives in
  `open-questions.md` under a "Context notes" tail section if it
  changes a bundle decision; otherwise drop it.
