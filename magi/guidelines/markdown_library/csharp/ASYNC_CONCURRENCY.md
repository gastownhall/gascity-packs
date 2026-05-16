# Async/Await and Concurrency

### Async Method Design

Every async method accepting I/O or delay must accept `CancellationToken`:

```csharp
public async Task<Order?> GetOrderAsync(Guid id, CancellationToken cancellationToken) {
    return await _context.Orders.FirstOrDefaultAsync(o => o.Id == id, cancellationToken);
}
```

Use the `Async` suffix for async methods returning `Task` or `ValueTask`.

### Blocking Async Code

**Forbidden in application paths**:
- `.Result`
- `.Wait()`
- `.GetAwaiter().GetResult()`

**Exception**: Top-level `Main` entry point in console apps.

### ConfigureAwait Usage

| Context | Rule |
|:--------|:-----|
| Library code | **Always** use `.ConfigureAwait(false)` |
| Application code (ASP.NET Core, console apps) | Omit `ConfigureAwait(false)` (no synchronization context) |

```csharp
public async Task<string> FetchDataAsync(string url, CancellationToken ct) {
    using var response = await _httpClient.GetAsync(url, ct).ConfigureAwait(false);
    return await response.Content.ReadAsStringAsync(ct).ConfigureAwait(false);
}
```

### Parallel Async Operations

```csharp
public async Task<(User, List<Order>)> LoadUserDataAsync(Guid userId, CancellationToken ct) {
    var userTask = _userRepository.GetAsync(userId, ct);
    var ordersTask = _orderRepository.GetByUserAsync(userId, ct);
    await Task.WhenAll(userTask, ordersTask).ConfigureAwait(false);
    return (await userTask, await ordersTask);
}
```

### ValueTask Usage

```csharp
public ValueTask<Order?> GetCachedOrderAsync(Guid id, CancellationToken ct) {
    if (_cache.TryGetValue(id, out var order)) return ValueTask.FromResult<Order?>(order);
    return new ValueTask<Order?>(LoadOrderAsync(id, ct));
}
```

**Never await a `ValueTask` multiple times; never store it for later awaiting.**

### Channels for Producer-Consumer

```csharp
public sealed class OrderProcessor {
    private readonly Channel<Order> _channel = Channel.CreateBounded<Order>(new BoundedChannelOptions(1000) {
        FullMode = BoundedChannelFullMode.Wait,
        SingleReader = true,
        SingleWriter = false,
    });

    public async ValueTask EnqueueAsync(Order order, CancellationToken ct) => await _channel.Writer.WriteAsync(order, ct);

    public async Task ProcessAsync(CancellationToken ct) {
        await foreach (var order in _channel.Reader.ReadAllAsync(ct)) {
            await ProcessOrderAsync(order, ct);
        }
    }
}
```

### Async Disposable Resources

```csharp
await using var connection = await _connectionFactory.CreateAsync(ct);
await using var transaction = await connection.BeginTransactionAsync(ct);
```

---
[Back to Overview](./OVERVIEW.md)
