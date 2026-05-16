# Anti-Patterns and Prohibited Practices

This section catalogs common containerization mistakes and their correct alternatives.

## Image Anti-Patterns

### Fat Images

**Anti-pattern**: Including build tools, source code, and debugging utilities in production images.

```dockerfile
# PROHIBITED: Build tools in runtime image
FROM mcr.microsoft.com/dotnet/sdk:8.0
COPY . .
RUN dotnet build
CMD ["dotnet", "run"]
```

**Correct approach**: Multi-stage build with minimal runtime image.

### Unversioned Base Images

**Anti-pattern**: Using `latest` or unversioned tags.

```dockerfile
# PROHIBITED: Unpredictable base
FROM node:latest

# CORRECT: Pinned version
FROM node:20.10.0-alpine3.18
```

### Secrets in Images

**Anti-pattern**: Embedding secrets in images.

```dockerfile
# PROHIBITED: Secret in environment
ENV DATABASE_PASSWORD=supersecret

# PROHIBITED: Secret in file
COPY ./secrets/credentials.json /app/credentials.json
```

**Correct approach**: Inject secrets at runtime via environment variables or mounted secrets.

### Root User

**Anti-pattern**: Running as root.

```dockerfile
# PROHIBITED: Implicitly runs as root
FROM mcr.microsoft.com/dotnet/aspnet:8.0
COPY --from=build /app .
ENTRYPOINT ["dotnet", "MyApp.dll"]
```

**Correct approach**: Explicit non-root user.

```dockerfile
FROM mcr.microsoft.com/dotnet/aspnet:8.0
USER $APP_UID
COPY --from=build /app .
ENTRYPOINT ["dotnet", "MyApp.dll"]
```

## Application Anti-Patterns

### File-Based State

**Anti-pattern**: Relying on local filesystem for persistent state.

```csharp
// PROHIBITED: State in local file
File.WriteAllText("/app/data/user_count.txt", count.ToString());
```

**Correct approach**: Use external storage (database, object storage, cache).

### Hardcoded Configuration

**Anti-pattern**: Environment-specific values in code.

```csharp
// PROHIBITED: Hardcoded connection string
var connectionString = "Host=prod-db.example.com;Database=app;";
```

**Correct approach**: Configuration from environment.

```csharp
var connectionString = builder.Configuration.GetConnectionString("Default");
```

### Blocking Startup

**Anti-pattern**: Long-running initialization blocking container readiness.

```csharp
// PROHIBITED: Blocking startup
public void Configure(IApplicationBuilder app)
{
    LoadAllDataIntoMemory();  // Takes 5 minutes
    WarmUpCaches();           // Takes 2 minutes
}
```

**Correct approach**: Background initialization with health check gates.

### Ignoring Signals

**Anti-pattern**: Not handling SIGTERM.

```csharp
// PROHIBITED: Infinite loop ignoring cancellation
while (true)
{
    ProcessNextItem();
    Thread.Sleep(1000);
}
```

**Correct approach**: Respect cancellation tokens.

```csharp
while (!stoppingToken.IsCancellationRequested)
{
    await ProcessNextItemAsync(stoppingToken);
    await Task.Delay(1000, stoppingToken);
}
```

## Operational Anti-Patterns

### No Resource Limits

**Anti-pattern**: Running containers without resource limits.

```yaml
# PROHIBITED: Unbounded resources
services:
  app:
    image: myapp
```

**Correct approach**: Explicit limits.

```yaml
services:
  app:
    image: myapp
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
```

### No Health Checks

**Anti-pattern**: No health endpoints or container health checks.

**Correct approach**: Health checks at application and container level.

### Manual Deployments

**Anti-pattern**: SSH into servers to update containers.

**Correct approach**: Automated CI/CD pipeline with immutable deployments.

### Stateful Containers

**Anti-pattern**: Treating containers like VMs with persistent state.

**Correct approach**: Containers are ephemeral; externalize all state.

## Networking Anti-Patterns

### Hardcoded IPs

**Anti-pattern**: Using IP addresses instead of service discovery.

```csharp
// PROHIBITED: Hardcoded IP
var client = new HttpClient { BaseAddress = new Uri("http://10.0.0.15:8080") };
```

**Correct approach**: Use DNS/service names.

```csharp
var client = new HttpClient { BaseAddress = new Uri("http://order-service:8080") };
```

### Exposing Unnecessary Ports

**Anti-pattern**: Exposing all ports to host.

```yaml
# PROHIBITED: Database exposed to host in production
services:
  postgres:
    ports:
      - "5432:5432"
```

**Correct approach**: Internal-only networking for infrastructure.

```yaml
services:
  postgres:
    expose:
      - "5432"  # Only accessible within Docker network
```

---
[Back to Overview](./OVERVIEW.md)
