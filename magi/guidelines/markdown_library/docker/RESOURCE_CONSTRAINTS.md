# Resource Constraints

### Memory Limits

Set memory limits to prevent containers from exhausting host resources:

```bash
docker run --memory=512m --memory-swap=512m myimage
```

- `--memory`: Hard limit; container killed if exceeded.
- `--memory-swap`: Total memory + swap; set equal to `--memory` to disable swap.
- `--memory-reservation`: Soft limit; used for scheduling.

In Compose:
```yaml
services:
  app:
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 256M
```

.NET-specific configuration:
```dockerfile
ENV DOTNET_GCHeapHardLimitPercent=75
ENV DOTNET_RUNNING_IN_CONTAINER=true
```

### CPU Limits

```bash
docker run --cpus=1.5 myimage              # Limit to 1.5 CPU cores
docker run --cpu-shares=512 myimage        # Relative weight (default 1024)
docker run --cpuset-cpus=0,1 myimage       # Pin to specific cores
```

In Compose:
```yaml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '2.0'
        reservations:
          cpus: '0.5'
```

### Resource Sizing Guidelines

| Workload Type | CPU | Memory |
|:--------------|:----|:-------|
| Web API (light) | 100m–500m | 128Mi–512Mi |
| Web API (moderate) | 250m–1000m | 256Mi–1Gi |
| Background worker | 100m–500m | 256Mi–1Gi |
| Data processing | 500m–2000m | 512Mi–2Gi |

- Set limits based on actual resource usage plus headroom.
- Monitor resource consumption in staging before setting production limits.
- Limits too low cause OOM kills and throttling; limits too high waste resources.
- Start conservative and adjust based on metrics.

---
[Back to Overview](./OVERVIEW.md)
