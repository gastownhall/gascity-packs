# Error Handling and Result Patterns

### Exception Design

Use exceptions for **truly exceptional** conditions — failures that cannot be reasonably anticipated or recovered from at the call site:

```csharp
public sealed class OrderNotFoundException : Exception {
    public Guid OrderId { get; }
    public OrderNotFoundException(Guid orderId) : base($"Order {orderId} not found") => OrderId = orderId;
}
```

### Guard Clauses

```csharp
public void ProcessOrder(Order order, PaymentDetails payment) {
    ArgumentNullException.ThrowIfNull(order);
    ArgumentNullException.ThrowIfNull(payment);
    ArgumentOutOfRangeException.ThrowIfNegativeOrZero(order.Total);
    ArgumentException.ThrowIfNullOrWhiteSpace(order.CustomerId);
    // Implementation
}
```

### Result Pattern for Expected Failures

```csharp
public readonly record struct Result<T> {
    public T? Value { get; }
    public string? Error { get; }
    public bool IsSuccess => Error is null;
    private Result(T value) { Value = value; Error = null; }
    private Result(string error) { Value = default; Error = error; }
    public static Result<T> Success(T value) => new(value);
    public static Result<T> Failure(string error) => new(error);
    public TResult Match<TResult>(Func<T, TResult> onSuccess, Func<string, TResult> onFailure) =>
        IsSuccess ? onSuccess(Value!) : onFailure(Error!);
}
```

Usage:

```csharp
public Result<Order> CreateOrder(CreateOrderCommand command) {
    if (command.Lines.Count == 0) return Result<Order>.Failure("Order must have at least one line");
    if (command.Lines.Any(l => l.Quantity <= 0)) return Result<Order>.Failure("All quantities must be positive");
    var order = new Order { Id = Guid.NewGuid(), Lines = command.Lines.ToList() };
    return Result<Order>.Success(order);
}
```

### Exception Wrapping

```csharp
try {
    await _externalService.CallAsync(ct);
} catch (HttpRequestException ex) {
    throw new ExternalServiceException("External service call failed", ex);
}
```

### Never Swallow Exceptions

```csharp
try {
    await ProcessAsync(ct);
} catch (OperationCanceledException) {
    _logger.LogInformation("Operation was cancelled");
    throw;
} catch (Exception ex) {
    _logger.LogError(ex, "Unexpected error during processing");
    throw;
}
```

---
[Back to Overview](./OVERVIEW.md)
