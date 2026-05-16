# Migration Patterns

This section covers patterns for migrating existing applications to containers.

## Strangler Fig Pattern

Gradually replace monolith components with containerized services.

### Phase 1: Identify Extraction Candidates

- Components with distinct responsibilities
- Components with different scaling requirements
- Components with independent release cycles

### Phase 2: Create Facade

```csharp
// Facade that can route to monolith or new service
public class OrderService : IOrderService
{
    private readonly IOrderServiceLegacy _legacy;
    private readonly IOrderServiceNew _new;
    private readonly IFeatureFlags _flags;
    public async Task<Order> GetOrderAsync(int orderId)
    {
        if (_flags.UseNewOrderService)
        {
            return await _new.GetOrderAsync(orderId);
        }
        return await _legacy.GetOrderAsync(orderId);
    }
}
```

### Phase 3: Extract and Deploy

- Deploy containerized version alongside monolith
- Route increasing traffic to new service
- Monitor for parity
- Eventually remove from monolith

## Parallel Run Pattern

Run containerized and legacy versions simultaneously for validation.

### Implementation

```yaml
services:
  # New containerized version
  order-api-new:
    image: order-api:2.0

  # Shadow traffic to new version
  shadow-proxy:
    image: envoyproxy/envoy
    # Duplicate requests to both versions, compare responses
```

### Comparison Logic

```csharp
public class ShadowComparer : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken ct)
    {
        await foreach (var comparison in _comparisonQueue.ReadAllAsync(ct))
        {
            if (!ResponsesMatch(comparison.Legacy, comparison.New))
            {
                _logger.LogWarning("Response mismatch for request {RequestId}",
                    comparison.RequestId);
            }
        }
    }
}
```

## Database Migration Patterns

### Blue-Green Database Migration

1. Create new database with updated schema
2. Set up data replication from old to new
3. Switch application to new database
4. Stop replication, decommission old database

### Schema Migration in Containers

```dockerfile
# Migration container
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS migration
WORKDIR /src
COPY . .
RUN dotnet build

ENTRYPOINT ["dotnet", "ef", "database", "update"]
```

Run migration as init container or job before application deployment.

## Testing Migration

### Integration Testing

```csharp
public class ContainerizedIntegrationTests : IClassFixture<ContainerFixture>
{
    private readonly ContainerFixture _fixture;
    [Fact]
    public async Task OrderApi_CreateOrder_ReturnsCreated()
    {
        // Arrange
        var client = _fixture.CreateClient();
        var order = new CreateOrderRequest { /* ... */ };
        // Act
        var response = await client.PostAsJsonAsync("/api/orders", order);
        // Assert
        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
    }
}
```

### Container Test Fixtures

```csharp
public class ContainerFixture : IAsyncLifetime
{
    private IContainer _postgres;
    private IContainer _app;
    public async Task InitializeAsync()
    {
        _postgres = await new ContainerBuilder()
            .WithImage("postgres:16-alpine")
            .WithEnvironment("POSTGRES_PASSWORD", "test")
            .WithWaitStrategy(Wait.ForUnixContainer().UntilPortIsAvailable(5432))
            .BuildAsync();
        await _postgres.StartAsync();
        _app = await new ContainerBuilder()
            .WithImage("myapp:test")
            .WithEnvironment("ConnectionStrings__Default", GetConnectionString())
            .WithWaitStrategy(Wait.ForUnixContainer().UntilHttpRequestIsSucceeded("/health"))
            .BuildAsync();
        await _app.StartAsync();
    }
    public async Task DisposeAsync()
    {
        await _app.DisposeAsync();
        await _postgres.DisposeAsync();
    }
}
```

---
[Back to Overview](./OVERVIEW.md)
