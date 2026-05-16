# Source Generators

### JSON Source Generation

```csharp
[JsonSerializable(typeof(Order))]
[JsonSerializable(typeof(List<Order>))]
[JsonSourceGenerationOptions(
    PropertyNamingPolicy = JsonKnownNamingPolicy.CamelCase,
    DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
)]
public partial class AppJsonContext : JsonSerializerContext { }
```

### Logging Source Generation

```csharp
public static partial class LoggerExtensions {
    [LoggerMessage(
        EventId = 1000,
        Level = LogLevel.Information,
        Message = "Order {OrderId} created for customer {CustomerId}"
    )]
    public static partial void OrderCreated(this ILogger logger, Guid orderId, string customerId);
}
```

---
[Back to Overview](./OVERVIEW.md)
