# Operational Concerns

This section covers production operational requirements for containerized applications.

## Resource Limits

### Container Resource Configuration

Always set resource limits:

```yaml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 256M
```

### Resource Sizing Guidelines

| Workload Type      | CPU Request | CPU Limit | Memory Request | Memory Limit |
|--------------------|-------------|-----------|----------------|--------------|
| Web API (light)    | 100m        | 500m      | 128Mi          | 512Mi        |
| Web API (moderate) | 250m        | 1000m     | 256Mi          | 1Gi          |
| Background worker  | 100m        | 500m      | 256Mi          | 1Gi          |
| Data processing    | 500m        | 2000m     | 512Mi          | 2Gi          |

### Memory Configuration for .NET

.NET containers need memory configuration:

```dockerfile
# Set memory limits for garbage collection
ENV DOTNET_GCHeapHardLimit=0x40000000
# Or as percentage of container limit
ENV DOTNET_GCHeapHardLimitPercent=75
```

### CPU Configuration for .NET

```dockerfile
# Limit thread pool size based on container CPU
ENV DOTNET_PROCESSOR_COUNT=2
# Or let runtime detect container limits (default in .NET 8+)
ENV DOTNET_RUNNING_IN_CONTAINER=true
```

## Observability Integration

### Metrics Endpoint

Expose Prometheus-compatible metrics:

```csharp
// Install: dotnet add package OpenTelemetry.Exporter.Prometheus.AspNetCore
builder.Services.AddOpenTelemetry()
    .WithMetrics(metrics =>
    {
        metrics.AddAspNetCoreInstrumentation()
            .AddHttpClientInstrumentation()
            .AddRuntimeInstrumentation()
            .AddPrometheusExporter();
    });
app.MapPrometheusScrapingEndpoint("/metrics");
```

### Distributed Tracing

Configure OpenTelemetry tracing:

```csharp
builder.Services.AddOpenTelemetry()
    .WithTracing(tracing =>
    {
        tracing.AddAspNetCoreInstrumentation()
            .AddHttpClientInstrumentation()
            .AddSqlClientInstrumentation()
            .AddOtlpExporter(options =>
            {
                options.Endpoint = new Uri(builder.Configuration["Otlp:Endpoint"]!);
            });
    });
```

### Container Logging

Configure structured logging with container context:

```csharp
builder.Logging.AddJsonConsole(options =>
{
    options.IncludeScopes = true;
});
// Add container metadata to logs
builder.Services.AddSingleton<IEnricher>(sp =>
{
    return new ContainerEnricher(
        Environment.GetEnvironmentVariable("HOSTNAME") ?? "unknown",
        Environment.GetEnvironmentVariable("POD_NAME") ?? "unknown"
    );
});
```

## Security Hardening

### Read-Only Filesystem

Run containers with read-only root filesystem:

```yaml
services:
  app:
    read_only: true
    tmpfs:
      - /tmp
    volumes:
      - app_data:/app/data  # Only writable mount
```

### Drop Capabilities

Remove unnecessary Linux capabilities:

```yaml
services:
  app:
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE  # Only if binding to ports < 1024
```

### Security Context

```yaml
services:
  app:
    security_opt:
      - no-new-privileges:true
    user: "1000:1000"
```

### Secret Management

Never embed secrets in images. Inject at runtime:

```yaml
services:
  app:
    secrets:
      - db_password
      - api_key

secrets:
  db_password:
    external: true
  api_key:
    file: ./secrets/api_key.txt
```

In application code:

```csharp
// Read secret from mounted file
var dbPassword = File.ReadAllText("/run/secrets/db_password").Trim();
```

## Troubleshooting Containers

### Debugging Running Containers

```bash
# View logs
docker logs -f container_name
# Execute command in container
docker exec -it container_name /bin/sh
# View container processes
docker exec container_name ps aux
# View resource usage
docker stats container_name
# Inspect container configuration
docker inspect container_name
```

### Common Issues and Solutions

| Symptom                       | Likely Cause                          | Solution                            |
|-------------------------------|---------------------------------------|-------------------------------------|
| Container exits immediately   | Application crash on startup          | Check logs: `docker logs container` |
| Container exits with code 137 | Out of memory (OOMKilled)             | Increase memory limit               |
| Container exits with code 143 | Received SIGTERM (normal shutdown)    | Check orchestrator logs             |
| Connection refused to service | Service not ready or wrong hostname   | Check health, verify service name   |
| Permission denied             | Running as non-root, file permissions | Check file ownership in image       |
| DNS resolution failure        | Network configuration                 | Check network mode, DNS settings    |

### Debugging Dockerfile Builds

```bash
# Build with verbose output
docker build --progress=plain .
# Build to specific stage
docker build --target build -t debug-build .
# Run shell in build stage
docker run -it debug-build /bin/sh
# View layer history
docker history myapp:latest
```

## Sidecar Patterns

### Log Shipping Sidecar

```yaml
services:
  app:
    volumes:
      - logs:/var/log/app

  log-shipper:
    image: fluent/fluent-bit
    volumes:
      - logs:/var/log/app:ro
    environment:
      - FLUENT_ELASTICSEARCH_HOST=elasticsearch
```

### Metrics Collection Sidecar

```yaml
services:
  app:
    ports:
      - "8080:8080"

  metrics-agent:
    image: datadog/agent:latest
    environment:
      - DD_API_KEY=${DD_API_KEY}
      - DD_APM_ENABLED=true
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
```

### Proxy Sidecar

```yaml
services:
  app:
    # App listens on localhost only
    environment:
      - ASPNETCORE_URLS=http://127.0.0.1:8080

  envoy:
    image: envoyproxy/envoy:v1.28-latest
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./envoy.yaml:/etc/envoy/envoy.yaml
```

---
[Back to Overview](./OVERVIEW.md)
