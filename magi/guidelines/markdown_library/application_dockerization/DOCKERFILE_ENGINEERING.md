# Dockerfile Engineering

This section covers the implementation patterns for production-quality Dockerfiles.

## Base Image Selection

### Base Image Hierarchy

Choose base images based on security, size, and compatibility requirements:

| Image Type      | Size      | Security Updates  | Use Case                              |
|-----------------|-----------|-------------------|---------------------------------------|
| `scratch`       | 0 MB      | N/A               | Statically compiled Go, Rust binaries |
| `distroless`    | 2-20 MB   | Google-maintained | Runtime-only, no shell needed         |
| `alpine`        | 5-50 MB   | Fast, community   | Small images, musl libc acceptable    |
| `slim` variants | 50-150 MB | Debian-based      | Standard compatibility, smaller size  |
| `full` variants | 200+ MB   | Debian/Ubuntu     | Build stages, debugging, full tooling |

### .NET Base Images

For .NET applications, Microsoft provides purpose-built images:

| Image                                   | Purpose                    | Size (approx) |
|-----------------------------------------|----------------------------|---------------|
| `mcr.microsoft.com/dotnet/sdk`          | Building .NET applications | 800+ MB       |
| `mcr.microsoft.com/dotnet/aspnet`       | Running ASP.NET Core apps  | 200-300 MB    |
| `mcr.microsoft.com/dotnet/runtime`      | Running console apps       | 150-200 MB    |
| `mcr.microsoft.com/dotnet/runtime-deps` | Self-contained apps        | 50-100 MB     |

Version tags:
- `8.0` - Latest .NET 8 patch
- `8.0-alpine` - Alpine-based, smaller
- `8.0-jammy` - Ubuntu 22.04 based
- `8.0-bookworm-slim` - Debian 12 slim

### Base Image Selection Decision Tree

```
What type of application?
├── Statically compiled (Go, Rust with musl)
│   └── Use scratch or distroless/static
├── .NET application
│   ├── ASP.NET Core web app → mcr.microsoft.com/dotnet/aspnet
│   ├── Console application → mcr.microsoft.com/dotnet/runtime
│   └── Self-contained deployment → mcr.microsoft.com/dotnet/runtime-deps
├── Node.js application
│   ├── Production only → node:XX-alpine or node:XX-slim
│   └── Needs native modules → node:XX (full Debian)
├── Python application
│   ├── Pure Python → python:XX-slim
│   └── Needs compiled packages → python:XX
└── Java application
    ├── Modern JVM → eclipse-temurin:XX-jre-alpine
    └── Needs full JDK → eclipse-temurin:XX-jdk
```

### Base Image Anti-Patterns

**Using `latest` tag**:
```dockerfile
# PROHIBITED: Unpredictable, breaks reproducibility
FROM node:latest

# CORRECT: Pin to specific version
FROM node:20.10-alpine3.18
```

**Using development images in production**:
```dockerfile
# PROHIBITED: Includes compilers, debuggers, unnecessary tools
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS runtime

# CORRECT: Use runtime image for final stage
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
```

**Using unverified images**:
```dockerfile
# PROHIBITED: Unknown provenance, security risk
FROM randomuser/dotnet-app-base

# CORRECT: Use official images from verified publishers
FROM mcr.microsoft.com/dotnet/aspnet:8.0
```

## Multi-Stage Build Patterns

Multi-stage builds separate build-time dependencies from runtime, producing smaller, more secure images.

### Basic Multi-Stage Pattern

```dockerfile
# Stage 1: Build
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

# Copy project files and restore dependencies
COPY *.csproj .
RUN dotnet restore

# Copy source and build
COPY . .
RUN dotnet publish -c Release -o /app/publish --no-restore

# Stage 2: Runtime
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app

# Copy only published output
COPY --from=build /app/publish .

# Configure runtime
ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080

ENTRYPOINT ["dotnet", "MyApp.dll"]
```

### Layer Caching Optimization

Order Dockerfile instructions from least-frequently-changed to most-frequently-changed:

```dockerfile
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

# Layer 1: Project files (changes infrequently)
COPY ["src/MyApp/MyApp.csproj", "src/MyApp/"]
COPY ["src/MyApp.Core/MyApp.Core.csproj", "src/MyApp.Core/"]
COPY ["src/MyApp.Infrastructure/MyApp.Infrastructure.csproj", "src/MyApp.Infrastructure/"]
COPY ["Directory.Build.props", "."]
COPY ["Directory.Packages.props", "."]

# Layer 2: Dependency restore (changes when packages change)
RUN dotnet restore "src/MyApp/MyApp.csproj"

# Layer 3: Source code (changes frequently)
COPY . .

# Layer 4: Build (always runs when source changes)
RUN dotnet publish "src/MyApp/MyApp.csproj" -c Release -o /app/publish --no-restore
```

### Advanced Multi-Stage: Build and Test

```dockerfile
# Stage 1: Build
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY . .
RUN dotnet restore
RUN dotnet build -c Release --no-restore

# Stage 2: Test (can be skipped in CI if tests run separately)
FROM build AS test
RUN dotnet test -c Release --no-build --verbosity normal

# Stage 3: Publish
FROM build AS publish
RUN dotnet publish -c Release -o /app/publish --no-restore --no-build

# Stage 4: Runtime
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
COPY --from=publish /app/publish .
ENTRYPOINT ["dotnet", "MyApp.dll"]
```

Build targets:
- `docker build --target build .` - Build only
- `docker build --target test .` - Build and test
- `docker build .` - Full build including runtime image

### Multi-Stage with Native Dependencies

When the application requires native libraries during build:

```dockerfile
# Stage 1: Build with native dependencies
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
RUN apt-get update && apt-get install -y \
    libgdiplus \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY . .
RUN dotnet publish -c Release -o /app/publish

# Stage 2: Runtime with only required native libs
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
RUN apt-get update && apt-get install -y \
    libgdiplus \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=build /app/publish .
ENTRYPOINT ["dotnet", "MyApp.dll"]
```

## Dockerfile Best Practices

### USER and Security

Never run containers as root in production:

```dockerfile
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime

# Create non-root user
RUN groupadd --gid 1000 appgroup \
    && useradd --uid 1000 --gid appgroup --shell /bin/false appuser

WORKDIR /app
COPY --from=build --chown=appuser:appgroup /app/publish .

# Switch to non-root user
USER appuser

ENTRYPOINT ["dotnet", "MyApp.dll"]
```

For .NET 8+, Microsoft's images include a non-root user:

```dockerfile
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
COPY --from=build /app/publish .

# Use the built-in non-root user
USER $APP_UID

ENTRYPOINT ["dotnet", "MyApp.dll"]
```

### Health Checks

Define container health checks for orchestration:

```dockerfile
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
COPY --from=build /app/publish .

# Health check using curl
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:8080/health || exit 1

ENTRYPOINT ["dotnet", "MyApp.dll"]
```

For images without curl, use a .NET health check endpoint:

```dockerfile
# Health check using wget (available in most images)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1
```

### Labels and Metadata

Add metadata for image management:

```dockerfile
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime

LABEL org.opencontainers.image.title="MyApp" \
      org.opencontainers.image.description="Order processing service" \
      org.opencontainers.image.version="1.2.3" \
      org.opencontainers.image.vendor="Acme Corp" \
      org.opencontainers.image.source="https://github.com/acme/myapp"

WORKDIR /app
COPY --from=build /app/publish .
ENTRYPOINT ["dotnet", "MyApp.dll"]
```

### Signal Handling

Ensure the application receives signals correctly:

```dockerfile
# CORRECT: exec form - PID 1 receives signals directly
ENTRYPOINT ["dotnet", "MyApp.dll"]

# INCORRECT: shell form - shell is PID 1, signals may not propagate
ENTRYPOINT dotnet MyApp.dll
```

### Minimize Layer Count

Combine related commands to reduce layers:

```dockerfile
# INEFFICIENT: Multiple layers
RUN apt-get update
RUN apt-get install -y curl
RUN apt-get install -y wget
RUN rm -rf /var/lib/apt/lists/*

# EFFICIENT: Single layer
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        wget \
    && rm -rf /var/lib/apt/lists/*
```

### .dockerignore

Always include a .dockerignore file to prevent unwanted files from entering the build context:

```
# .dockerignore
**/.git
**/.vs
**/.vscode
**/bin
**/obj
**/node_modules
**/.env
**/*.md
**/Dockerfile*
**/.dockerignore
**/docker-compose*.yml
**/*.log
**/coverage
**/test-results
```

## Environment Configuration

### Environment Variables

Design for configuration via environment variables:

```dockerfile
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app

# Define defaults that can be overridden
ENV ASPNETCORE_ENVIRONMENT=Production \
    ASPNETCORE_URLS=http://+:8080 \
    ConnectionStrings__DefaultConnection="" \
    Logging__LogLevel__Default=Information

COPY --from=build /app/publish .
EXPOSE 8080
ENTRYPOINT ["dotnet", "MyApp.dll"]
```

### Secret Management

Never embed secrets in images:

```dockerfile
# PROHIBITED: Secret in image
ENV DATABASE_PASSWORD=supersecret123

# PROHIBITED: Secret in build arg persisted to image
ARG DB_PASSWORD
ENV DATABASE_PASSWORD=$DB_PASSWORD

# CORRECT: Secret injected at runtime
ENV DATABASE_PASSWORD=""
# Override with: docker run -e DATABASE_PASSWORD=actual_secret
```

For build-time secrets (e.g., private NuGet feeds):

```dockerfile
# Use Docker BuildKit secrets
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

# Mount secret at build time only - not persisted in image
RUN --mount=type=secret,id=nuget_config,target=/root/.nuget/NuGet/NuGet.Config \
    dotnet restore

COPY . .
RUN dotnet publish -c Release -o /app/publish
```

Build with: `docker build --secret id=nuget_config,src=./NuGet.Config .`

---
[Back to Overview](./OVERVIEW.md)
