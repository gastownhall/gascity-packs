# Making Future-Proof Decisions

### Signs You Might Need to Migrate

| From             | To          | Trigger                                  |
|------------------|-------------|------------------------------------------|
| SQL              | Cosmos DB   | Single-node write limits, global latency |
| In-process cache | Redis       | Multi-instance cache coherence           |
| Storage Queues   | Service Bus | Need DLQ, scheduling, sessions           |
| RabbitMQ         | Event Hubs  | Throughput limits, replay requirements   |
| Any              | Snowflake   | Analytics queries impacting OLTP         |

### Migration Mitigation Strategies

**Abstract Data Access**:
```csharp
// Repository interface doesn't expose storage technology
public interface IOrderRepository
{
    Task<Order?> GetByIdAsync(Guid orderId, CancellationToken ct);
    Task<IReadOnlyList<Order>> GetByCustomerAsync(Guid customerId, CancellationToken ct);
    Task AddAsync(Order order, CancellationToken ct);
}

// Implementation can change without affecting consumers
public class SqlOrderRepository : IOrderRepository { ... }
public class CosmosOrderRepository : IOrderRepository { ... }
```

**Feature Flags for Gradual Migration**:
```csharp
if (_featureFlags.UseNewDatabase)
{
    return await _cosmosRepository.GetByIdAsync(orderId, ct);
}
else
{
    return await _sqlRepository.GetByIdAsync(orderId, ct);
}
```

**Dual-Write During Migration**:
```csharp
// Write to both, read from old, compare
await _sqlRepository.AddAsync(order, ct);
await _cosmosRepository.AddAsync(order, ct);

var sqlOrder = await _sqlRepository.GetByIdAsync(order.Id, ct);
var cosmosOrder = await _cosmosRepository.GetByIdAsync(order.Id, ct);
_validator.AssertEqual(sqlOrder, cosmosOrder); // Log discrepancies
```

---
[Back to Overview](./OVERVIEW.md)
