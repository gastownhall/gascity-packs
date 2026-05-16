# Data Access Patterns

### Repository Pattern with Specification

```csharp
public interface IRepository<T> where T : class
{
    Task<T?> GetByIdAsync(object id, CancellationToken ct);
    Task<IReadOnlyList<T>> ListAsync(ISpecification<T> spec, CancellationToken ct);
    Task<int> CountAsync(ISpecification<T> spec, CancellationToken ct);
    Task AddAsync(T entity, CancellationToken ct);
    Task UpdateAsync(T entity, CancellationToken ct);
    Task DeleteAsync(T entity, CancellationToken ct);
}

public interface ISpecification<T>
{
    Expression<Func<T, bool>>? Criteria { get; }
    List<Expression<Func<T, object>>> Includes { get; }
    Expression<Func<T, object>>? OrderBy { get; }
    Expression<Func<T, object>>? OrderByDescending { get; }
    int? Skip { get; }
    int? Take { get; }
}

// Usage
var spec = new OrdersForCustomerSpec(customerId)
    .WithStatus(OrderStatus.Completed)
    .OrderByDescending(o => o.CreatedAt)
    .Paginate(page: 1, pageSize: 20);

var orders = await _orderRepository.ListAsync(spec, ct);
```

### Unit of Work Pattern

```csharp
public interface IUnitOfWork : IDisposable
{
    IOrderRepository Orders { get; }
    IProductRepository Products { get; }
    ICustomerRepository Customers { get; }

    Task<int> SaveChangesAsync(CancellationToken ct);
    Task BeginTransactionAsync(CancellationToken ct);
    Task CommitTransactionAsync(CancellationToken ct);
    Task RollbackTransactionAsync(CancellationToken ct);
}

// Usage
await using var uow = _unitOfWorkFactory.Create();
await uow.BeginTransactionAsync(ct);

try
{
    var order = await uow.Orders.GetByIdAsync(orderId, ct);
    order.Status = OrderStatus.Confirmed;
    await uow.Orders.UpdateAsync(order, ct);

    var customer = await uow.Customers.GetByIdAsync(order.CustomerId, ct);
    customer.OrderCount++;
    await uow.Customers.UpdateAsync(customer, ct);

    await uow.SaveChangesAsync(ct);
    await uow.CommitTransactionAsync(ct);
}
catch
{
    await uow.RollbackTransactionAsync(ct);
    throw;
}
```

### CQRS Pattern

Separate read and write models:

```csharp
// Commands
public record CreateOrderCommand(Guid CustomerId, List<OrderItem> Items) : ICommand<Guid>;

public class CreateOrderHandler : ICommandHandler<CreateOrderCommand, Guid>
{
    private readonly IOrderRepository _repository;
    private readonly IEventPublisher _events;

    public async Task<Guid> HandleAsync(CreateOrderCommand command, CancellationToken ct)
    {
        var order = Order.Create(command.CustomerId, command.Items);
        await _repository.AddAsync(order, ct);
        await _events.PublishAsync(new OrderCreatedEvent(order.Id), ct);
        return order.Id;
    }
}

// Queries
public record GetOrderQuery(Guid OrderId) : IQuery<OrderDto>;

public class GetOrderHandler : IQueryHandler<GetOrderQuery, OrderDto>
{
    private readonly IReadOnlyRepository<OrderReadModel> _readRepository;

    public async Task<OrderDto> HandleAsync(GetOrderQuery query, CancellationToken ct)
    {
        // Query optimized read model, possibly from different store
        var readModel = await _readRepository.GetByIdAsync(query.OrderId, ct);
        return _mapper.Map<OrderDto>(readModel);
    }
}
```

---
[Back to Overview](./OVERVIEW.md)
