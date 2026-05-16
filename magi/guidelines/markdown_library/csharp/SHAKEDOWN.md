# Shakedown

### Definition

Shakedown is the **first controlled, end-to-end execution** of a .NET solution under real operating conditions:
- `IHost` fully built
- DI container resolved
- EF Core connected to a real database
- MassTransit connected to a real broker

It is integration validation of the **composed system** — not xUnit unit tests, not BenchmarkDotNet performance measurement.

Shakedown exercises `IHost` and its DI graph against real infrastructure: real SQL Server / PostgreSQL via `Testcontainers.NET`, real RabbitMQ / Kafka via `Testcontainers.NET`, real Redis, real Azure Storage via Azurite. **Unit tests with mocks cannot detect DI registration drift, EF Core migration gaps, `IOptions` binding failures, or `IHostedService` ordering bugs.**

### Preflight vs Shakedown vs Testing

| Stage | Question | Requirement |
|:------|:---------|:------------|
| Preflight | Static prerequisites | `dotnet build` succeeds, `dotnet format` verifies, connection strings present, env vars resolved, health endpoint skeleton returns 200 |
| **Shakedown** | **Integration validation under real conditions** | **`IHost` composes, DI graph resolves, EF Core migrates, brokers connect, known-good commands flow end-to-end through MediatR / MassTransit pipelines, `IHostedService` activation completes, health checks report healthy beyond simple liveness** |
| Testing | Behavioral and performance verification | xUnit facts, integration tests with `WebApplicationFactory`, BenchmarkDotNet, load tests |

### Three Forms

| Form | Description |
|:-----|:------------|
| Dedicated test project | A `Shakedown.IntegrationTests` project using xUnit and `Testcontainers.NET`, run via `dotnet test --filter Category=Shakedown` in CI before deploy |
| Hosted service startup | `IHostedService` registered before the web host accepts traffic. `StartAsync` runs the full shakedown sequence and fails fast (throws) on any fail-blocking result, preventing Kestrel from binding |
| `dotnet run --shakedown` mode | Entry point inspects args for `--shakedown` and routes to a `ShakedownRunner` that exits with an integer classification code (0 pass, 1 fail-blocking, 2 fail-nonblocking, 3 inconclusive) |

### Mandatory Triggers

- First-ever deployment of a new service or worker
- Major refactor of the `IHost` composition root or `Program.cs`
- New package added that registers services via extension methods (`AddDbContext`, `AddMassTransit`, `AddOpenTelemetry`)
- EF Core version bump, provider swap, or migration addition
- .NET major/minor version upgrade
- Kafka/RabbitMQ broker version change, MassTransit version bump, consumer/producer refactor
- Database provider change, cloud provider move, new base image
- Repair after production incident affecting integration boundaries
- Extended dormancy of a service whose dependencies have had security updates

### Non-Triggers

- Bug fixes confined to a single class with no DI or async boundary changes
- Nullable annotation fixes, XML doc updates, file-scoped namespace migrations
- Configuration value changes within the validated `IOptions<T>` schema
- Test-only changes in test projects
- Routine deployments of an unchanged service with unchanged dependencies

### Validation Categories

1. **`IHost` wiring and DI graph resolution** — every registered service resolves via `IServiceProvider.GetRequiredService` without `CaptureStartupErrors`; scoped services instantiate inside request scope; no singleton captures scoped dependencies.
2. **EF Core migrations and `DbContext` connectivity** — `Database.MigrateAsync` applies migrations to the shakedown database; `DbContext` executes a known-good query and deserializes results into entity types.
3. **Message broker connectivity** — MassTransit / Kafka / RabbitMQ bus starts, declares topology, publishes a known-good message, and the corresponding consumer handles it end-to-end with the expected `IConsumer<T>` pipeline filters.
4. **Background service activation** — every `IHostedService.StartAsync` completes within its budget; `BackgroundService.ExecuteAsync` enters its loop; hosted services ordered via `IHostedLifecycleService` fire in the expected sequence.
5. **Health checks beyond liveness** — `IHealthCheck` implementations report `Healthy` for database, broker, cache, and downstream services; `/health/ready` returns 200 only after shakedown passes.
6. **`IOptions<T>` and `IConfiguration` propagation** — configuration binds from `appsettings`, env vars, Azure App Configuration, or Key Vault into strongly-typed options and reaches consuming services via `IOptions`, `IOptionsSnapshot`, or `IOptionsMonitor`.
7. **Error handling paths** — Polly policies (retry, circuit breaker, timeout) engage on transient failures; `ExceptionHandler` middleware catches unhandled exceptions; logging captures context with correlation IDs.
8. **Side effect correctness** — writes target the correct table, messages land on the correct exchange/topic, blob uploads land at the correct container; idempotency keys honored where claimed.

### Execution Principles

- **Conservative inputs** — representative commands, queries, and events with known expected outcomes; not fuzz, not AutoFixture randomness, not load test fixtures
- **Progressive stress** — start with a single request through the happy path; add concurrent `IHttpClientFactory` calls and parallel consumers incrementally; stop on the first failure
- **Controlled environment** — `Testcontainers.NET` for database, broker, cache; sandbox credentials for external APIs; in-process `WebApplicationFactory` for HTTP surfaces when appropriate
- **Observable execution** — Serilog or `Microsoft.Extensions.Logging` at Debug level with structured output; OpenTelemetry traces exported to console exporter; every `Task` awaited and timing captured
- **Known-good inputs** — fixed set of commands and events with known expected outputs committed alongside the shakedown project
- **No optimization during shakedown** — do not tune ThreadPool, do not change connection pool sizes, do not enable Server GC variants
- **`CancellationToken` everywhere** — shakedown respects the runner's `CancellationToken` on every async call

### Execution Sequence

```text
Step 1:  Confirm preflight passes — dotnet build with -warnaserror succeeds, dotnet format --verify-no-changes passes
Step 2:  Start Testcontainers for every real dependency and await readiness
Step 3:  Build the IHost with the real composition root pointed at Testcontainers endpoints
Step 4:  Resolve every registered service from IServiceProvider to detect DI graph errors eagerly
Step 5:  Apply EF Core migrations and execute a known-good query
Step 6:  Start all IHostedService instances and verify each reports ready
Step 7:  Publish a known-good message and assert the consumer handled it
Step 8:  Hit every health check endpoint and assert Healthy
Step 9:  Verify all logs, traces, and metrics captured expected events
Step 10: Stop the host, dispose Testcontainers, assert no orphaned resources
Step 11: Record observations and classify results
```

### Reference Hosted-Service Implementation

```csharp
namespace Company.Product.Host.Shakedown;

using System.Diagnostics;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

/// <summary>
/// Runs the integration shakedown against real infrastructure before the web host accepts traffic.
/// Throws on fail-blocking classification to prevent Kestrel from binding.
/// </summary>
public sealed class ShakedownHostedService(
    IServiceProvider services,
    ILogger<ShakedownHostedService> logger
) : IHostedService {
    public async Task StartAsync(CancellationToken cancellationToken) {
        var stopwatch = Stopwatch.StartNew();
        logger.LogInformation("Shakedown starting");
        await using var scope = services.CreateAsyncScope();
        var provider = scope.ServiceProvider;
        await ValidateDatabaseAsync(provider, cancellationToken).ConfigureAwait(false);
        await ValidateBrokerAsync(provider, cancellationToken).ConfigureAwait(false);
        await ValidateHealthChecksAsync(provider, cancellationToken).ConfigureAwait(false);
        logger.LogInformation("Shakedown passed in {Elapsed}ms", stopwatch.ElapsedMilliseconds);
    }

    public Task StopAsync(CancellationToken cancellationToken) => Task.CompletedTask;

    private static async Task ValidateDatabaseAsync(IServiceProvider provider, CancellationToken ct) {
        var db = provider.GetRequiredService<AppDbContext>();
        await db.Database.MigrateAsync(ct).ConfigureAwait(false);
        var probe = await db.Probes.AsNoTracking().FirstOrDefaultAsync(ct).ConfigureAwait(false);
        if (probe is null) {
            throw new ShakedownBlockingException("Probe row missing after migrations");
        }
    }

    private static async Task ValidateBrokerAsync(IServiceProvider provider, CancellationToken ct) {
        var publisher = provider.GetRequiredService<IShakedownPublisher>();
        await publisher.PublishAsync(new ShakedownPing(Guid.NewGuid()), ct).ConfigureAwait(false);
    }

    private static async Task ValidateHealthChecksAsync(IServiceProvider provider, CancellationToken ct) {
        var service = provider.GetRequiredService<Microsoft.Extensions.Diagnostics.HealthChecks.HealthCheckService>();
        var report = await service.CheckHealthAsync(ct).ConfigureAwait(false);
        if (report.Status != Microsoft.Extensions.Diagnostics.HealthChecks.HealthStatus.Healthy) {
            throw new ShakedownBlockingException($"Health status {report.Status}");
        }
    }
}

public sealed class ShakedownBlockingException(string message) : Exception(message);
public sealed record ShakedownPing(Guid CorrelationId);
public interface IShakedownPublisher {
    Task PublishAsync(ShakedownPing ping, CancellationToken cancellationToken);
}
```

### Result Classification

- **Pass** — `IHost` composes; every category green; ready for testing or deployment.
- **Fail-blocking** — Integration fault prevents correct operation. Fix the code and re-run from step 1.
- **Fail-nonblocking** — Observed issue that does not prevent operation. Log to tracker with full diagnostic context and proceed.
- **Inconclusive** — Environment or input limitation prevented validation of a critical path. Adjust and re-run the specific validation.

### Required Artifacts

- **Execution log** — full Serilog/`ILogger` output with structured fields, correlation IDs, timestamps
- **Result summary** — classification per validation category as machine-readable JSON
- **Issue list** — every anomaly classified blocking/non-blocking/deferred with reproduction context
- **Environment snapshot** — runtime version (`dotnet --info`), NuGet package lockfile hash, Testcontainers image digests, `IConfiguration` snapshot with secrets redacted

### Anti-Patterns (Forbidden)

- Skipping shakedown after a "small" DI registration tweak or `Program.cs` refactor
- Packing dozens of xUnit `Fact`s into the shakedown runner and treating coverage as the goal
- Running shakedown against Moq, NSubstitute, or `InMemoryDatabase` providers instead of `Testcontainers.NET`
- Tuning thread pool, GC mode, or EF Core query batching during shakedown
- Running shakedown without capturing logs, summary, or environment snapshot
- Catching and swallowing exceptions inside the shakedown runner instead of classifying them

---
[Back to Overview](./OVERVIEW.md)
