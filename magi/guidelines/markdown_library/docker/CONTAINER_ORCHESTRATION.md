# Container Orchestration

### Kubernetes Probe Mapping

| Probe Type | Endpoint | Purpose |
|:-----------|:---------|:--------|
| liveness | `/health/live` | Container restart if unhealthy |
| readiness | `/health/ready` | Traffic routing when ready |
| startup | `/health/startup` | Initial startup grace period |

### Init Containers for Setup Tasks

```yaml
initContainers:
  - name: migrate-db
    image: myapp:latest
    command: ["python", "manage.py", "migrate"]
```

Use init containers for database migrations, configuration fetching, or volume preparation that must complete before the main container starts.

---
[Back to Overview](./OVERVIEW.md)
