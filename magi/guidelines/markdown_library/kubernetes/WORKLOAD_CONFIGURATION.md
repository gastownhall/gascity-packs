# Workload Configuration

### Deployment Fundamentals

Every Deployment must specify:

- Explicit replica count based on availability requirements and load expectations.
- Resource requests and limits for all containers.
- Liveness and readiness probes appropriate to the application.
- Pod disruption budget for controlled voluntary disruptions.
- Update strategy matching deployment risk tolerance.

### Replica Considerations

- **Minimum 2 replicas** for any production workload.
- **3 replicas** for critical services requiring zone redundancy.
- HorizontalPodAutoscaler for variable load; set `minReplicas` to availability floor.
- Single replica acceptable only for development or singleton controllers with leader election.

### Pod Specification Standards

```yaml
spec:
  containers:
  - name: app
    image: registry.example.com/app:v1.2.3
    resources:
      requests:
        cpu: 100m
        memory: 256Mi
      limits:
        cpu: 500m
        memory: 512Mi
    ports:
    - containerPort: 8080
      protocol: TCP
    livenessProbe:
      httpGet:
        path: /healthz
        port: 8080
      initialDelaySeconds: 10
      periodSeconds: 15
      timeoutSeconds: 5
      failureThreshold: 3
    readinessProbe:
      httpGet:
        path: /ready
        port: 8080
      initialDelaySeconds: 5
      periodSeconds: 10
      timeoutSeconds: 3
      failureThreshold: 3
    securityContext:
      runAsNonRoot: true
      runAsUser: 1000
      readOnlyRootFilesystem: true
      allowPrivilegeEscalation: false
      capabilities:
        drop:
        - ALL
```

### Init Containers

Containers that run to completion before app containers start. Use for:

- Database migrations.
- Configuration downloading.
- Dependency checking.
- Volume permissions setup.

```yaml
spec:
  initContainers:
  - name: migration
    image: registry.example.com/migrator:v1.0.0
    command: ['sh', '-c', '/app/migrate.sh']
    resources:
      requests:
        cpu: 100m
        memory: 256Mi
      limits:
        cpu: 200m
        memory: 512Mi
```

### Sidecar Patterns

**Logging sidecar:**

```yaml
- name: log-forwarder
  image: fluentbit/fluent-bit:2.0
  volumeMounts:
  - name: shared-logs
    mountPath: /var/log
  resources:
    requests:
      cpu: 20m
      memory: 64Mi
    limits:
      cpu: 100m
      memory: 128Mi
```

**Proxy sidecar (auth, TLS, service mesh):**

```yaml
- name: envoy-proxy
  image: envoyproxy/envoy:v1.25
  ports:
  - containerPort: 15001
    protocol: TCP
  resources:
    requests:
      cpu: 50m
      memory: 128Mi
    limits:
      cpu: 200m
      memory: 256Mi
```

### StatefulSets

Use StatefulSets when workloads require:

- Stable network identity (predictable pod names).
- Ordered deployment and scaling.
- Persistent storage with pod affinity.

Considerations:

- Pod management policy `Parallel` for faster scaling when ordering not required.
- Headless service for stable DNS names.
- Volume claim templates for per-replica storage.
- Update strategy `RollingUpdate` with `partition` for canary deployments.

### DaemonSets

DaemonSets ensure one pod per node for:

- Log collection agents.
- Monitoring exporters.
- Network plugins.
- Security agents.

Apply node selectors or affinity to target specific node pools. Use tolerations to schedule on tainted nodes (system pool, GPU nodes) when necessary.

### Jobs and CronJobs

| Parameter | Purpose |
|:----------|:--------|
| `backoffLimit` | Prevent infinite retry loops |
| `activeDeadlineSeconds` | Bound execution time |
| `ttlSecondsAfterFinished` | Clean up completed jobs |
| `concurrencyPolicy: Forbid` | (CronJob) Prevent overlapping executions |

Assign resource requests/limits — Jobs compete for cluster resources like any workload.

---
[Back to Overview](./OVERVIEW.md)
