# Resource Management

### Requests vs Limits

- **Requests**: guaranteed allocation; scheduler uses requests for placement decisions. Setting requests too low causes overcommitment and resource contention.
- **Limits**: maximum consumption; exceeding memory limit triggers OOM kill, exceeding CPU limit triggers throttling. Setting limits too low causes unnecessary throttling or kills.

### Sizing Methodology

| Step | Action |
|:----:|:-------|
| 1 | Run application under typical load; observe actual CPU and memory consumption |
| 2 | Set requests at p90 utilization plus 20% buffer |
| 3 | Set limits at 2–3× requests for burstable workloads; closer to requests for consistent workloads |
| 4 | Monitor throttling and OOM events; adjust based on production behavior |

### Quality of Service Classes

| QoS Class | Condition | Eviction Priority |
|:----------|:----------|:------------------|
| **Guaranteed** | Requests equal limits for all containers | Last (lowest priority for eviction) |
| Burstable | Requests set, limits higher or unset | Middle |
| BestEffort | No requests or limits | First (highest priority) — **forbidden in production** |

Critical workloads should be Guaranteed class.

### Vertical Pod Autoscaler

VPA in **recommendation mode** informs manual tuning rather than automatic mode (which causes pod restarts):

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: app-vpa
spec:
  targetRef:
    apiVersion: "apps/v1"
    kind: Deployment
    name: app
  updatePolicy:
    updateMode: "Off"
  resourcePolicy:
    containerPolicies:
    - containerName: app
      minAllowed:
        cpu: 50m
        memory: 128Mi
      maxAllowed:
        cpu: 2
        memory: 2Gi
```

### Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: app-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: app
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Pods
    pods:
      metric:
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: "1000"
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30
```

| Signal | Use |
|:-------|:----|
| CPU utilization (70–80%) | Default for CPU-bound workloads |
| Memory | Generally not a good scaling metric — pressure indicates incorrect sizing, not scaling need |
| Custom metrics (RPS, queue depth, business KPIs) | Preferred for accurate scaling signals |

Configure stabilization windows to prevent thrashing during load fluctuations.

---
[Back to Overview](./OVERVIEW.md)
