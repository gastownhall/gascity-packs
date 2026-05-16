# Minimal APIs

### Route Groups

```csharp
var app = WebApplication.Create(args);

var orders = app.MapGroup("/api/orders")
    .RequireAuthorization()
    .WithOpenApi();

orders.MapGet("/", async (IOrderService service, CancellationToken ct) =>
    await service.GetAllAsync(ct));

orders.MapGet("/{id:guid}", async (Guid id, IOrderService service, CancellationToken ct) =>
    await service.GetByIdAsync(id, ct) is { } order
        ? Results.Ok(order)
        : Results.NotFound());

orders.MapPost("/", async (CreateOrderRequest request, IOrderService service, CancellationToken ct) => {
    var order = await service.CreateAsync(request, ct);
    return Results.Created($"/api/orders/{order.Id}", order);
});
```

### TypedResults for Compile-Time Safety

```csharp
app.MapGet("/api/orders/{id:guid}", async Task<Results<Ok<Order>, NotFound>> (
    Guid id,
    IOrderService service,
    CancellationToken ct) =>
{
    var order = await service.GetByIdAsync(id, ct);
    return order is not null
        ? TypedResults.Ok(order)
        : TypedResults.NotFound();
});
```

---
[Back to Overview](./OVERVIEW.md)
