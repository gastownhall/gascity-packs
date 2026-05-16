# Logging and Observability

### Structured Logging

```csharp
logger.LogInformation("Order {OrderId} created for customer {CustomerId} with total {Total:C}", order.Id, order.CustomerId, order.Total);
```

**Never use string interpolation in log message templates** — it defeats structured logging and creates GC pressure.

### Log Levels

| Level | Usage |
|:------|:------|
| Trace | Detailed diagnostic information, typically only in development |
| Debug | Internal state useful during debugging |
| Information | Significant events in normal operation |
| Warning | Unexpected but handled conditions |
| Error | Failures affecting current operation |
| Critical | Failures affecting system stability |

### High-Performance Logging (Source Generators)

```csharp
public static partial class LoggerExtensions {
    [LoggerMessage(EventId = 1000, Level = LogLevel.Information, Message = "Order {OrderId} processed successfully")]
    public static partial void OrderProcessed(this ILogger logger, Guid orderId);

    [LoggerMessage(Level = LogLevel.Error, Message = "Failed to process order {OrderId}")]
    public static partial void OrderProcessingFailed(this ILogger logger, Guid orderId, Exception exception);
}
```

### Correlation and Tracing

```csharp
public sealed class CorrelationMiddleware(RequestDelegate next) {
    public async Task InvokeAsync(HttpContext context) {
        var correlationId = context.Request.Headers["X-Correlation-ID"].FirstOrDefault() ?? Guid.NewGuid().ToString();
        context.Items["CorrelationId"] = correlationId;
        context.Response.Headers["X-Correlation-ID"] = correlationId;
        using (logger.BeginScope(new Dictionary<string, object> { ["CorrelationId"] = correlationId })) {
            await next(context);
        }
    }
}
```

### Metrics

```csharp
public sealed class OrderMetrics {
    private readonly Counter<long> _ordersCreated;
    private readonly Histogram<double> _orderProcessingDuration;

    public OrderMetrics(IMeterFactory meterFactory) {
        var meter = meterFactory.Create("Company.Product.Orders");
        _ordersCreated = meter.CreateCounter<long>("orders.created", "orders", "Number of orders created");
        _orderProcessingDuration = meter.CreateHistogram<double>("orders.processing.duration", "ms", "Order processing duration");
    }

    public void RecordOrderCreated() => _ordersCreated.Add(1);
    public void RecordProcessingDuration(double milliseconds) => _orderProcessingDuration.Record(milliseconds);
}
```

---
[Back to Overview](./OVERVIEW.md)
