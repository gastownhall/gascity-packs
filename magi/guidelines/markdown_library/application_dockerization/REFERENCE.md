# Reference

Quick reference tables and checklists for containerization.

## Containerization Readiness Checklist

Before containerizing an application:

- Application writes logs to stdout/stderr, not files
- Configuration is injectable via environment variables
- No hardcoded file paths or hostnames
- Graceful shutdown handling implemented
- Health check endpoints available
- State externalized to databases/caches
- Secrets not embedded in code or config files
- Dependencies are documented and versionable
- Application starts within 30 seconds
- Application shuts down within 30 seconds

## Dockerfile Checklist

For production Dockerfiles:

- Multi-stage build separates build from runtime
- Base image pinned to specific version
- Non-root user configured
- Health check defined
- Labels with image metadata
- .dockerignore excludes unnecessary files
- No secrets in build args or environment
- ENTRYPOINT uses exec form
- Single process per container
- Minimal layers for runtime stage

## .NET Version Migration Reference

| From   | To         | Key Changes                                             |
|--------|------------|---------------------------------------------------------|
| .NET 6 | .NET 8     | Port 8080 default, non-root user, globalization changes |
| .NET 7 | .NET 8     | Same as above                                           |
| .NET 8 | .NET 9     | Performance improvements, new APIs                      |
| Any    | Native AOT | Reflection limitations, smaller images, faster startup  |

## Common Ports Reference

| Service                 | Default Port | Container Recommendation   |
|-------------------------|--------------|----------------------------|
| ASP.NET Core (.NET 8+)  | 8080         | Use default                |
| ASP.NET Core (.NET 6/7) | 80           | Consider 8080 for non-root |
| PostgreSQL              | 5432         | Standard                   |
| SQL Server              | 1433         | Standard                   |
| Redis                   | 6379         | Standard                   |
| RabbitMQ                | 5672/15672   | AMQP/Management            |
| MongoDB                 | 27017        | Standard                   |

## Resource Sizing Reference

| Workload          | Memory    | CPU      | Notes               |
|-------------------|-----------|----------|---------------------|
| Minimal API       | 128-256Mi | 100-250m | Simple endpoints    |
| Typical API       | 256-512Mi | 250-500m | Database, caching   |
| Heavy API         | 512Mi-2Gi | 500m-2   | Complex processing  |
| Background worker | 256-512Mi | 100-500m | Depends on workload |
| Batch processor   | 1-4Gi     | 1-4      | Data-intensive      |

## Style Summary

| Element           | Required Practice                                              |
|-------------------|----------------------------------------------------------------|
| **Base Images**   | Pinned versions, minimal runtime images, official sources only |
| **Multi-Stage**   | Separate build and runtime stages, optimize layer caching      |
| **Configuration** | Environment variables, no hardcoded values, secrets at runtime |
| **Health**        | Liveness and readiness endpoints, container health checks      |
| **Logging**       | stdout/stderr, structured JSON, no file logging                |
| **Shutdown**      | SIGTERM handling, graceful drain, configurable timeout         |
| **Security**      | Non-root user, minimal capabilities, read-only filesystem      |
| **Resources**     | Explicit limits and requests, .NET-specific memory settings    |
| **State**         | Externalized to databases/caches, containers are ephemeral     |
| **Networking**    | Service discovery by name, no hardcoded IPs                    |
| **Testing**       | Container-based integration tests, parity with production      |
| **CI/CD**         | Automated builds, vulnerability scanning, immutable tags       |

Following these patterns produces containerized applications that are portable, scalable, secure, and operationally sound. The container is the complete deployment unit. Configuration lives outside. State is externalized. Containers start fast and stop gracefully.

**Apply these principles universally when containerizing any application, regardless of language or framework.**

---
[Back to Overview](./OVERVIEW.md)
