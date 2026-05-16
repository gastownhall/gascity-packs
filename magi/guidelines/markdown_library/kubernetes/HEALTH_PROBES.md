# Health Probes

### Liveness Probes

Detect when a container needs restart. Initial delay must account for startup time. Failure threshold prevents premature restarts.

| Probe Type | Use For |
|:-----------|:--------|
| `httpGet` | HTTP services |
| `tcpSocket` | TCP services |
| `exec` | Custom health checks |

### Readiness Probes

Determine when a container is ready to accept traffic. Must validate all dependencies. Faster checks than liveness.

### Startup Probes

Handle slow-starting containers. Suppress liveness/readiness probes until startup succeeds:

```yaml
startupProbe:
  httpGet:
    path: /startup
    port: 8080
  initialDelaySeconds: 0
  periodSeconds: 10
  timeoutSeconds: 1
  successThreshold: 1
  failureThreshold: 30
```

**Every workload MUST declare all three probe types.** Together they catch crashes, slow boots, and gradual degradation.

---
[Back to Overview](./OVERVIEW.md)
