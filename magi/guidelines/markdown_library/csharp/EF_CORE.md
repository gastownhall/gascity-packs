# Entity Framework Core Patterns

### Always Async

```csharp
public async Task<List<Order>> GetOrdersAsync(string customerId, CancellationToken ct) {
    return await _context.Orders
        .Where(o => o.CustomerId == customerId)
        .OrderByDescending(o => o.CreatedAt)
        .ToListAsync(ct);
}
```

### AsNoTracking for Read-Only

```csharp
public async Task<Order?> GetOrderForDisplayAsync(Guid id, CancellationToken ct) {
    return await _context.Orders
        .AsNoTracking()
        .Include(o => o.Lines)
        .FirstOrDefaultAsync(o => o.Id == id, ct);
}
```

### AsSplitQuery for Multiple Includes

```csharp
var orders = await _context.Orders
    .AsSplitQuery()
    .Include(o => o.Lines)
    .Include(o => o.Customer)
    .Include(o => o.ShippingAddress)
    .ToListAsync(ct);
```

### Compiled Queries for Hot Paths

```csharp
private static readonly Func<AppDbContext, Guid, Task<Order?>> _getOrderById =
    EF.CompileAsyncQuery((AppDbContext context, Guid id) =>
        context.Orders.FirstOrDefault(o => o.Id == id));

public Task<Order?> GetByIdAsync(Guid id) => _getOrderById(_context, id);
```

---
[Back to Overview](./OVERVIEW.md)
