# DaemonSet deployment pattern

## What and why

One OTel Collector per Kubernetes node. Each Collector owns the
node-local sources (`hostmetrics`, `filelog`, `kubeletstats`,
`otlp` from pods on that node) and exports to a Netdata Parent
elsewhere, or to a local Netdata child running on the same node.

Pros:

- Lowest egress: node-local scraping stays on the node.
- Horizontal scaling is free: more nodes means more Collectors.
- Low blast radius: one Collector failure affects one node.

Cons:

- Hard to do cluster-wide logic in this pattern. Put cluster-scope
  receivers (e.g., `k8s_cluster`) in a separate Deployment.
- Per-node duplicated config.

## Minimal manifests

Namespace and RBAC (kubeletstats and k8sattributes both need it):

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: otel

---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: otel-collector-daemonset
  namespace: otel

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: otel-collector-daemonset
rules:
  - apiGroups: [""]
    resources: [pods, namespaces, nodes, nodes/stats, nodes/proxy]
    verbs: [get, list, watch]
  - apiGroups: ["apps"]
    resources: [replicasets, deployments]
    verbs: [get, list, watch]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: otel-collector-daemonset
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: otel-collector-daemonset
subjects:
  - kind: ServiceAccount
    name: otel-collector-daemonset
    namespace: otel
```

Config (`otel-collector-config.yaml`):

```yaml
receivers:
  otlp:
    protocols:
      grpc: { endpoint: 0.0.0.0:4317 }
      http: { endpoint: 0.0.0.0:4318 }
  hostmetrics:
    collection_interval: 10s
    scrapers:
      cpu: {}
      memory: {}
      disk: {}
      filesystem: {}
      network: {}
  kubeletstats:
    collection_interval: 20s
    auth_type: serviceAccount
    endpoint: https://${K8S_NODE_NAME}:10250
    insecure_skip_verify: true
    node: ${K8S_NODE_NAME}
  filelog:
    include: [/var/log/pods/*/*/*.log]
    include_file_path: true
    operators:
      - type: container

processors:
  memory_limiter:
    check_interval: 1s
    limit_percentage: 75
    spike_limit_percentage: 15
  k8sattributes:
    auth_type: serviceAccount
    passthrough: false
    extract:
      metadata:
        - k8s.namespace.name
        - k8s.pod.name
        - k8s.deployment.name
        - k8s.node.name
    pod_association:
      - sources:
          - from: resource_attribute
            name: k8s.pod.ip
      - sources:
          - from: connection
  resource:
    attributes:
      - key: cluster.name
        value: prod-us-east-1
        action: upsert
  batch:
    send_batch_size: 8192
    timeout: 10s

exporters:
  otlp/netdata:
    endpoint: netdata-parent.observability.svc:4317
    tls: { insecure: true }
    sending_queue:
      enabled: true
      queue_size: 5000

service:
  pipelines:
    metrics:
      receivers: [otlp, hostmetrics, kubeletstats]
      processors: [memory_limiter, k8sattributes, resource, batch]
      exporters: [otlp/netdata]
    logs:
      receivers: [otlp, filelog]
      processors: [memory_limiter, k8sattributes, resource, batch]
      exporters: [otlp/netdata]
```

The DaemonSet:

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: otel-collector
  namespace: otel
spec:
  selector:
    matchLabels: { app: otel-collector }
  template:
    metadata:
      labels: { app: otel-collector }
    spec:
      serviceAccountName: otel-collector-daemonset
      hostNetwork: true
      containers:
        - name: collector
          image: otel/opentelemetry-collector-contrib:0.109.0
          args: [--config=/conf/otel-collector-config.yaml]
          env:
            - name: K8S_NODE_NAME
              valueFrom:
                fieldRef: { fieldPath: spec.nodeName }
          resources:
            limits: { memory: 512Mi, cpu: 500m }
            requests: { memory: 128Mi, cpu: 100m }
          volumeMounts:
            - { name: config, mountPath: /conf }
            - { name: varlogpods, mountPath: /var/log/pods, readOnly: true }
            - { name: varlibdocker, mountPath: /var/lib/docker/containers, readOnly: true }
      volumes:
        - name: config
          configMap: { name: otel-collector }
        - name: varlogpods
          hostPath: { path: /var/log/pods }
        - name: varlibdocker
          hostPath: { path: /var/lib/docker/containers }
```

## What producer pods send to

With `hostNetwork: true` the Collector on each node listens on the
node's IP at 4317/4318. Producers running on the same node use the
downward API:

```yaml
env:
  - name: OTEL_EXPORTER_OTLP_ENDPOINT
    value: "http://$(HOST_IP):4317"
  - name: HOST_IP
    valueFrom: { fieldRef: { fieldPath: status.hostIP } }
```

## Sizing

- CPU: 100m-500m per node handles typical workloads.
- Memory: 128Mi-512Mi. `memory_limiter: 75%` keeps the pod from
  being OOMKilled.
- Disk: only `filelog` needs temp space for position files.
  Default lives in `/var/lib/otelcol`.
