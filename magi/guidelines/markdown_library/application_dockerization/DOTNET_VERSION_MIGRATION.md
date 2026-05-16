# .NET Version Migration

Containerization is an ideal time to upgrade .NET versions. This section covers migration from .NET 6 through .NET 10 in the container context.

## .NET Version Landscape

### Version Status and Container Implications

| Version | Status                     | Support Ends | Container Recommendation   |
|---------|----------------------------|--------------|----------------------------|
| .NET 6  | LTS (End of Life Nov 2024) | Nov 2024     | Migrate immediately        |
| .NET 7  | STS (End of Life)          | May 2024     | Migrate to .NET 8          |
| .NET 8  | LTS (Current)              | Nov 2026     | Recommended for production |
| .NET 9  | STS                        | May 2026     | For latest features        |
| .NET 10 | LTS (Preview)              | Nov 2028     | Preview only               |

### Migration Priority

For containerization projects:
1. If on .NET 6 or earlier: Migrate to .NET 8 (LTS)
2. If on .NET 7: Migrate to .NET 8 (LTS)
3. New projects: Start with .NET 8; consider .NET 9 for specific features

## .NET 6 to .NET 8 Migration

### Project File Updates

Update the target framework:

```xml
<!-- Before: .NET 6 -->
<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup>
    <TargetFramework>net6.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
</Project>

<!-- After: .NET 8 -->
<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
</Project>
```

### Dockerfile Base Image Updates

```dockerfile
# Before: .NET 6
FROM mcr.microsoft.com/dotnet/sdk:6.0 AS build
# ...
FROM mcr.microsoft.com/dotnet/aspnet:6.0 AS runtime

# After: .NET 8
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
# ...
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
```

### Breaking Changes Affecting Containerization

**Port Configuration**:

.NET 8 changes the default port:
- .NET 6: Default port 80/443
- .NET 8: Default port 8080 (non-root friendly)

```dockerfile
# .NET 6 (old behavior)
EXPOSE 80
ENV ASPNETCORE_URLS=http://+:80

# .NET 8 (new default)
EXPOSE 8080
ENV ASPNETCORE_URLS=http://+:8080
```

**Non-Root User**:

.NET 8 images include a built-in non-root user:

```dockerfile
# .NET 8: Use the built-in non-root user
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
COPY --from=build /app/publish .

USER $APP_UID
ENTRYPOINT ["dotnet", "MyApp.dll"]
```

**Globalization Invariant Mode**:

.NET 8 Alpine images default to invariant globalization. If your app requires full globalization:

```dockerfile
FROM mcr.microsoft.com/dotnet/aspnet:8.0-alpine AS runtime

# Install ICU for full globalization support
RUN apk add --no-cache icu-libs
ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=false
```

### API Changes Affecting Containerized Apps

**Minimal API Changes**:

```csharp
// .NET 6
app.MapGet("/", () => "Hello World");
// .NET 8: Same syntax, but new features available
app.MapGet("/", () => "Hello World")
   .WithName("GetRoot")
   .WithOpenApi();  // New in .NET 7+
```

**Configuration Binding**:

```csharp
// .NET 6: Allowed null sources
builder.Configuration.AddJsonFile("appsettings.json", optional: true);
// .NET 8: Stricter binding validation - ensure files exist or mark optional
builder.Configuration.AddJsonFile("appsettings.json", optional: true, reloadOnChange: false);
```

**HTTP Client Changes**:

```csharp
// .NET 6: Default behavior
services.AddHttpClient<IMyClient, MyClient>();
// .NET 8: Consider using resilience patterns
services.AddHttpClient<IMyClient, MyClient>()
    .AddStandardResilienceHandler();  // New in .NET 8
```

### Performance Improvements

.NET 8 provides significant container-relevant improvements:

- **Native AOT**: Compile to native code for faster startup
- **Dynamic PGO**: Runtime optimization enabled by default
- **Frozen Collections**: Optimized immutable collections
- **Time abstraction**: `TimeProvider` for testable time-dependent code

Enable Dynamic PGO in container:

```dockerfile
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
ENV DOTNET_TieredPGO=1
ENV DOTNET_ReadyToRun=0
```

## .NET 8 to .NET 9 Migration

### Key Changes for Containers

**Build Performance**:
- Faster restore and build times
- Improved incremental build in containers

**Runtime Improvements**:
- Better garbage collection for containerized workloads
- Improved thread pool for container CPU limits

### Dockerfile Updates

```dockerfile
# Update to .NET 9
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /src
COPY . .
RUN dotnet publish -c Release -o /app/publish

FROM mcr.microsoft.com/dotnet/aspnet:9.0 AS runtime
WORKDIR /app
COPY --from=build /app/publish .
USER $APP_UID
ENTRYPOINT ["dotnet", "MyApp.dll"]
```

### API Changes

```csharp
// .NET 9: Enhanced LINQ methods
var results = items
    .CountBy(x => x.Category)  // New in .NET 9
    .Where(g => g.Value > 5);
// .NET 9: New TimeSpan methods
var duration = TimeSpan.FromSeconds(90);
var formatted = duration.ToString("h'h 'm'm 's's'");  // Enhanced formatting
```

## Native AOT Deployment

Native AOT compiles .NET to native code, eliminating the need for the .NET runtime in the container.

### When to Use Native AOT

**Good candidates**:
- Microservices with simple dependencies
- Serverless functions (fast cold start)
- CLI tools
- High-density container deployments

**Poor candidates**:
- Applications using reflection-heavy libraries
- Applications with runtime code generation
- Entity Framework Core (limited support)
- SignalR (not supported)

### Native AOT Dockerfile

```dockerfile
# Build stage with AOT compilation
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
RUN apt-get update && apt-get install -y clang zlib1g-dev

WORKDIR /src
COPY . .
RUN dotnet publish -c Release -r linux-x64 -o /app/publish

# Runtime stage: minimal base image
FROM mcr.microsoft.com/dotnet/runtime-deps:8.0 AS runtime
WORKDIR /app
COPY --from=build /app/publish .
USER $APP_UID
ENTRYPOINT ["./MyApp"]
```

Project file for Native AOT:

```xml
<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <PublishAot>true</PublishAot>
    <InvariantGlobalization>true</InvariantGlobalization>
  </PropertyGroup>
</Project>
```

### AOT Size Comparison

| Deployment Type          | Image Size (approx) | Startup Time |
|--------------------------|---------------------|--------------|
| Standard aspnet:8.0      | 220 MB              | 500-1000 ms  |
| Alpine aspnet:8.0-alpine | 110 MB              | 500-1000 ms  |
| Self-contained           | 100-150 MB          | 300-500 ms   |
| Native AOT               | 30-50 MB            | 50-100 ms    |

## Migration Verification

### Validation Checklist

After migration, verify:

1. **Build succeeds**:
   ```bash
   docker build -t myapp:test .
   ```

2. **Application starts**:
   ```bash
   docker run -d --name test myapp:test
   docker logs test
   ```

3. **Health check passes**:
   ```bash
   docker inspect --format='{{.State.Health.Status}}' test
   ```

4. **API responds correctly**:
   ```bash
   curl http://localhost:8080/health
   ```

5. **No runtime warnings**:
   ```bash
   docker logs test 2>&1 | grep -i "warn\|error"
   ```

### Performance Baseline

Capture performance metrics before and after migration:

```bash
# Startup time
time docker run --rm myapp:test dotnet MyApp.dll --help

# Memory usage
docker stats --no-stream myapp

# Image size
docker images myapp
```

---
[Back to Overview](./OVERVIEW.md)
