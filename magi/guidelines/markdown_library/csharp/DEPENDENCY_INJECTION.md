# Dependency Injection and Composition

### Constructor Injection

Dependencies are injected through constructors. **Service location is prohibited.** Property injection and method injection for required dependencies are prohibited.

```csharp
public sealed class OrderService(IOrderRepository repository, IPaymentGateway paymentGateway, ILogger<OrderService> logger) : IOrderService {
    public async Task<Order> ProcessAsync(CreateOrderCommand command, CancellationToken ct) {
        logger.LogInformation("Processing order for customer {CustomerId}", command.CustomerId);
        var order = await repository.CreateAsync(command, ct);
        await paymentGateway.ChargeAsync(order.Total, command.PaymentMethod, ct);
        return order;
    }
}
```

### Service Registration

```csharp
public static class ServiceCollectionExtensions {
    public static IServiceCollection AddOrderServices(this IServiceCollection services) {
        services.AddScoped<IOrderRepository, OrderRepository>();
        services.AddScoped<IOrderService, OrderService>();
        services.AddSingleton<IPaymentGateway, StripePaymentGateway>();
        services.AddTransient<IEmailSender, SmtpEmailSender>();
        return services;
    }
}
```

### Lifetime Selection

| Lifetime | Use For | Constraints |
|:---------|:--------|:------------|
| **Singleton** | Stateless services, configuration, caches | Must be thread-safe |
| **Scoped** | Per-request state, database contexts, unit of work | Cannot depend on transient services |
| **Transient** | Lightweight, stateless operations | No shared state between instances |

### Interface Segregation

```csharp
public interface IOrderReader {
    Task<Order?> GetByIdAsync(Guid id, CancellationToken ct);
    Task<IReadOnlyList<Order>> GetByCustomerAsync(string customerId, CancellationToken ct);
}

public interface IOrderWriter {
    Task<Order> CreateAsync(CreateOrderCommand command, CancellationToken ct);
    Task UpdateAsync(Order order, CancellationToken ct);
}

public interface IOrderRepository : IOrderReader, IOrderWriter { }
```

### Keyed Services

```csharp
services.AddKeyedScoped<IPaymentProcessor, StripeProcessor>("stripe");
services.AddKeyedScoped<IPaymentProcessor, PayPalProcessor>("paypal");

public sealed class PaymentService([FromKeyedServices("stripe")] IPaymentProcessor processor) { }
```

### Options Pattern

```csharp
public sealed class SmtpOptions {
    public required string Host { get; init; }
    public required int Port { get; init; }
    public required string Username { get; init; }
    public required string Password { get; init; }
}

services.Configure<SmtpOptions>(configuration.GetSection("Smtp"));

public sealed class EmailSender(IOptions<SmtpOptions> options) {
    private readonly SmtpOptions _options = options.Value;
}
```

---
[Back to Overview](./OVERVIEW.md)
