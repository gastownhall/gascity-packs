# Health Checks and Lifecycle

### Health Check Configuration

Define health checks in Dockerfile for container orchestration:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1
```

Parameters:
- `--interval`: Time between checks (default 30s)
- `--timeout`: Maximum time for check to complete (default 30s)
- `--start-period`: Grace period for container startup (default 0s)
- `--retries`: Consecutive failures before unhealthy (default 3)

### Health Check Commands

- Exit code 0: Healthy
- Exit code 1: Unhealthy
- Exit code 2: Reserved (do not use)

Use lightweight checks that verify the application is ready to serve traffic:

```dockerfile
HEALTHCHECK CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1
```

For images without curl/wget, use application-specific health commands or include a minimal health check binary.

### Compose Healthcheck with Dependencies

```yaml
services:
  app:
    depends_on:
      db:
        condition: service_healthy
  db:
    image: postgres
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user"]
      interval: 5s
      timeout: 5s
      retries: 5
      start_period: 10s
```

### Health Check Endpoint Types

| Endpoint | Purpose |
|:---------|:--------|
| `/health/live` | Process is running |
| `/health/ready` | Can accept traffic |
| `/health/startup` | Initial startup complete |

Standard response format:
```json
{
  "status": "healthy",
  "checks": {
    "database": "healthy",
    "redis": "healthy"
  },
  "version": "1.2.3",
  "timestamp": "2024-01-20T10:30:00Z"
}
```

### Graceful Shutdown

Applications must handle SIGTERM for graceful shutdown:
- Stop accepting new requests.
- Complete in-flight requests within timeout.
- Close database connections cleanly.
- Exit with code 0.

Configure stop timeout at runtime:
```bash
docker run --stop-timeout 30 myimage
docker stop --time 30 container_name
```

### Lifecycle Hooks

Docker provides limited lifecycle hooks. For complex startup/shutdown logic:
- Use entrypoint scripts for initialization.
- Implement signal handlers in the application for cleanup.
- Consider init containers in Kubernetes for pre-start setup.

---
[Back to Overview](./OVERVIEW.md)
