# Type Design and Member Definitions

### Class Design Principles

- **Prefer `sealed` by default**; inheritance requires explicit design and documentation
- Use `abstract` only when defining true polymorphic hierarchies with shared behavior
- Avoid deep inheritance chains; prefer composition and interface implementation
- Mark classes with no intended subclasses as `sealed` to enable compiler optimizations

### Member Ordering Within Types

1. Constants and static readonly fields
2. Instance fields (private, then protected)
3. Constructors (static, then instance by parameter count ascending)
4. Properties (public, then protected, then private)
5. Methods (public, then protected, then private; group by functionality)
6. Operators and conversions
7. Nested types

### Method Signatures

Single-line when under 250 characters:

```csharp
public async Task<Order> GetByIdAsync(Guid id, CancellationToken ct) => await _repository.FindAsync(id, ct);
```

Multi-line when exceeding the limit:

```csharp
public async Task<Result<OrderConfirmation>> SubmitOrderAsync(
    CreateOrderCommand command,
    CancellationToken cancellationToken,
) {
    ArgumentNullException.ThrowIfNull(command);
    // Implementation
}
```

### Property Patterns

Use auto-properties for simple state; expression-bodied for computed values:

```csharp
public sealed class Order {
    public required Guid Id { get; init; }
    public required string CustomerId { get; init; }
    public IReadOnlyList<OrderLine> Lines { get; init; } = [];
    public decimal Total => Lines.Sum(l => l.Quantity * l.UnitPrice);
    public bool IsEmpty => Lines.Count == 0;
}
```

### Primary Constructors

Use primary constructors for dependency injection and simple parameter capture:

```csharp
public sealed class OrderService(IOrderRepository repository, ILogger<OrderService> logger) : IOrderService {
    public async Task<Order?> GetByIdAsync(Guid id, CancellationToken ct) {
        logger.LogDebug("Fetching order {OrderId}", id);
        return await repository.FindAsync(id, ct);
    }
}
```

Capture to fields only when the parameter needs modification or when the primary constructor parameter would shadow a member name.

### Required Members

```csharp
public sealed class Order {
    public required Guid Id { get; init; }
    public required string CustomerId { get; init; }
    public required decimal Total { get; init; }
}
```

### Collection Expressions (C# 12)

```csharp
int[] numbers = [1, 2, 3, 4, 5];
List<string> names = ["Alice", "Bob", "Charlie"];
ImmutableArray<int> immutable = [1, 2, 3];
// Spread operator
int[] combined = [..first, ..second, 99];
```

### Expression-bodied Members

```csharp
public string FullName => $"{FirstName} {LastName}";
public override string ToString() => $"Order {Id}: {Total:C}";
public static Order Empty => new() { Id = Guid.Empty, CustomerId = string.Empty };
```

Avoid expression bodies for methods with side effects or complex logic.

---
[Back to Overview](./OVERVIEW.md)
