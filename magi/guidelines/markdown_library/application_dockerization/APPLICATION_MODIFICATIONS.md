# Application Modifications

Containerization often requires application code changes to work correctly in container environments.

## Logging Configuration

### Container Logging Principles

Containers write logs to stdout/stderr. The container runtime captures these streams and forwards them to the logging infrastructure.

**Anti-pattern**: Writing to log files inside the container:

```csharp
// PROHIBITED: File-based logging in containers
Log.Logger = new LoggerConfiguration()
    .WriteTo.File("/var/log/app/application.log")
    .CreateLogger();
```

Problems:
- Logs lost when container terminates
- Logs not visible to orchestration platform
- Log rotation complexity inside containers

**Correct pattern**: Console/stdout logging:

```csharp
// CORRECT: Console logging for containers
Log.Logger = new LoggerConfiguration()
    .WriteTo.Console(new JsonFormatter())
    .CreateLogger();
// Or with Microsoft.Extensions.Logging
builder.Logging.AddJsonConsole();
```

### Structured Logging

Use structured (JSON) logging for machine parsing:

```csharp
// Configure JSON console logging
builder.Logging.AddJsonConsole(options =>
{
    options.JsonWriterOptions = new JsonWriterOptions
    {
        Indented = false
    };
    options.TimestampFormat = "yyyy-MM-ddTHH:mm:ss.fffZ";
});
```

Output:
```json
{"Timestamp":"2024-06-20T10:30:45.123Z","Level":"Information","Message":"Order processed","OrderId":"12345","CustomerId":"C-789"}
```

### Log Level Configuration

Make log levels configurable via environment:

```csharp
// appsettings.json
{
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "Microsoft.AspNetCore": "Warning"
    }
  }
}
```

Override via environment variable:
```bash
docker run -e Logging__LogLevel__Default=Debug myapp
```

## Health Endpoints

### Implementing Health Checks

Add health check endpoints for container orchestration:

```csharp
// Program.cs
builder.Services.AddHealthChecks()
    .AddCheck("self", () => HealthCheckResult.Healthy())
    .AddNpgSql(connectionString, name: "database")
    .AddRedis(redisConnection, name: "redis")
    .AddRabbitMQ(rabbitConnection, name: "rabbitmq");
app.MapHealthChecks("/health", new HealthCheckOptions
{
    ResponseWriter = WriteHealthCheckResponse
});
app.MapHealthChecks("/health/ready", new HealthCheckOptions
{
    Predicate = check => check.Tags.Contains("ready"),
    ResponseWriter = WriteHealthCheckResponse
});
app.MapHealthChecks("/health/live", new HealthCheckOptions
{
    Predicate = _ => false  // Only checks if app is running
});
```

### Health Check Response

```csharp
private static Task WriteHealthCheckResponse(HttpContext context, HealthReport report)
{
    context.Response.ContentType = "application/json";
    var response = new
    {
        status = report.Status.ToString(),
        checks = report.Entries.Select(e => new
        {
            name = e.Key,
            status = e.Value.Status.ToString(),
            duration = e.Value.Duration.TotalMilliseconds
        }),
        totalDuration = report.TotalDuration.TotalMilliseconds
    };
    return context.Response.WriteAsJsonAsync(response);
}
```

### Kubernetes Probe Mapping

| Probe Type    | Health Endpoint | Purpose                                                          |
|---------------|-----------------|------------------------------------------------------------------|
| **Liveness**  | `/health/live`  | Is the process running? Restart if not.                          |
| **Readiness** | `/health/ready` | Can the app handle requests? Remove from load balancer if not.   |
| **Startup**   | `/health/ready` | Has the app finished starting? Don't check liveness until ready. |

## Graceful Shutdown

### Handling SIGTERM

Containers receive SIGTERM on shutdown. The application must handle this signal:

```csharp
// Program.cs
var app = builder.Build();
var lifetime = app.Services.GetRequiredService<IHostApplicationLifetime>();
lifetime.ApplicationStopping.Register(() =>
{
    Log.Information("Application is shutting down...");
    // Stop accepting new requests
    // Wait for in-flight requests to complete
});
lifetime.ApplicationStopped.Register(() =>
{
    Log.Information("Application stopped");
    Log.CloseAndFlush();
});
await app.RunAsync();
```

### Background Service Shutdown

Background services must respect cancellation:

```csharp
public class OrderProcessorService : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                var order = await _queue.DequeueAsync(stoppingToken);
                await ProcessOrderAsync(order, stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                _logger.LogInformation("Order processor shutting down gracefully");
                break;
            }
        }
    }
}
```

### Shutdown Timeout Configuration

Configure adequate shutdown timeout:

```csharp
builder.WebHost.ConfigureKestrel(options =>
{
    options.Limits.KeepAliveTimeout = TimeSpan.FromSeconds(120);
    options.Limits.RequestHeadersTimeout = TimeSpan.FromSeconds(30);
});
builder.Host.ConfigureHostOptions(options =>
{
    options.ShutdownTimeout = TimeSpan.FromSeconds(30);
});
```

In Dockerfile or orchestration:
```yaml
# Kubernetes: Give app 30 seconds to shut down
terminationGracePeriodSeconds: 30
```

## Configuration Management

### Environment-Based Configuration

Structure configuration for container deployment:

```csharp
// Program.cs
var builder = WebApplication.CreateBuilder(args);
// Configuration sources (lowest to highest priority):
// 1. appsettings.json (baked into image)
// 2. appsettings.{Environment}.json (baked into image)
// 3. Environment variables (set at runtime)
// 4. Command line args (set at runtime)
builder.Configuration
    .AddJsonFile("appsettings.json", optional: false)
    .AddJsonFile($"appsettings.{builder.Environment.EnvironmentName}.json", optional: true)
    .AddEnvironmentVariables()
    .AddCommandLine(args);
```

### Connection String Handling

Design connection strings for container networking:

```json
{
  "ConnectionStrings": {
    "DefaultConnection": ""
  }
}
```

Override at runtime:
```bash
docker run -e ConnectionStrings__DefaultConnection="Host=db;Database=app;..." myapp
```

### Feature Flags and Runtime Configuration

For dynamic configuration, use external config services:

```csharp
builder.Configuration
    .AddAzureAppConfiguration(options =>
    {
        options.Connect(appConfigConnectionString)
            .ConfigureRefresh(refresh =>
            {
                refresh.Register("Settings:Sentinel", refreshAll: true)
                    .SetCacheExpiration(TimeSpan.FromMinutes(5));
            });
    });
```

## Database Connection Management

### Connection Pooling for Containers

Configure connection pooling appropriately for container density:

```csharp
builder.Services.AddDbContext<AppDbContext>(options =>
{
    options.UseNpgsql(connectionString, npgsqlOptions =>
    {
        npgsqlOptions.EnableRetryOnFailure(
            maxRetryCount: 3,
            maxRetryDelay: TimeSpan.FromSeconds(30),
            errorCodesToAdd: null);
    });
});
```

Pool size considerations:
- Containers may be dense (many containers per host)
- Default pool sizes (100 connections) multiply across containers
- Right-size pools: `Max Pool Size = (Container CPU * 2) + 1`

```
# Connection string with pool size
Host=db;Database=app;Username=user;Password=pass;Maximum Pool Size=20;
```

### Connection Resilience

Handle transient connection failures:

```csharp
builder.Services.AddDbContext<AppDbContext>(options =>
{
    options.UseSqlServer(connectionString, sqlOptions =>
    {
        sqlOptions.EnableRetryOnFailure(
            maxRetryCount: 5,
            maxRetryDelay: TimeSpan.FromSeconds(30),
            errorNumbersToAdd: new int[] { 4060, 40197, 40501, 40613 });
        sqlOptions.CommandTimeout(30);
    });
});
```

### Database Migration in Containers

Run migrations separately from application startup:

**Option 1: Init container (Kubernetes)**:
```yaml
initContainers:
  - name: migrate
    image: myapp:latest
    command: ["dotnet", "MyApp.dll", "--migrate"]
```

**Option 2: Separate migration job**:
```dockerfile
# Migration-specific entrypoint
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
COPY --from=build /app/publish .
ENTRYPOINT ["dotnet", "MyApp.dll", "--migrate"]
```

**Option 3: Startup migration (simple cases only)**:
```csharp
// Only for simple/dev scenarios - not recommended for production
using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    await db.Database.MigrateAsync();
}
```

## Distributed Caching

### Replacing In-Process Cache

Replace in-memory cache with distributed cache:

```csharp
// Before: In-process cache (doesn't scale)
builder.Services.AddMemoryCache();
// After: Distributed cache
builder.Services.AddStackExchangeRedisCache(options =>
{
    options.Configuration = builder.Configuration.GetConnectionString("Redis");
    options.InstanceName = "MyApp:";
});
```

### Cache Key Design for Containers

Design cache keys that work across container instances:

```csharp
public class ProductCacheService
{
    private readonly IDistributedCache _cache;
    // Cache key includes version for cache invalidation on deploy
    private const string KeyPrefix = "products:v1:";
    public async Task<Product?> GetProductAsync(int id, CancellationToken ct)
    {
        var key = $"{KeyPrefix}{id}";
        var cached = await _cache.GetStringAsync(key, ct);
        if (cached is not null)
        {
            return JsonSerializer.Deserialize<Product>(cached);
        }
        return null;
    }
}
```

## Session State

### Externalize Session Storage

Move session state out of the container:

```csharp
// Before: In-memory session (lost on container restart, not shared)
builder.Services.AddSession();
builder.Services.AddDistributedMemoryCache();
// After: Redis-backed session
builder.Services.AddStackExchangeRedisCache(options =>
{
    options.Configuration = builder.Configuration.GetConnectionString("Redis");
});
builder.Services.AddSession(options =>
{
    options.IdleTimeout = TimeSpan.FromMinutes(30);
    options.Cookie.HttpOnly = true;
    options.Cookie.IsEssential = true;
});
```

### Sticky Sessions Consideration

If external session storage is not feasible:
- Configure load balancer for sticky sessions
- Accept that container restarts lose sessions
- Document the limitation

---
[Back to Overview](./OVERVIEW.md)
