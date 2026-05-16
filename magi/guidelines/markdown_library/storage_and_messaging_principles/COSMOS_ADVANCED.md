# Cosmos DB Advanced Patterns

### Hierarchical Partition Keys

For scenarios where single partition key doesn't provide enough granularity:

```json
{
    "id": "order-123",
    "tenantId": "tenant-1",
    "year": 2024,
    "customerId": "customer-456",
    "items": [...]
}
```

Hierarchical partition key: `/tenantId/year/customerId`

Benefits:
- Queries within tenant/year are efficient
- Data naturally ages out by year
- Customer data co-located within tenant

### Materialized Views with Change Feed

```csharp
public class OrderSummaryProcessor : IChangeFeedProcessor
{
    public async Task ProcessChangesAsync(IReadOnlyList<OrderDocument> changes, CancellationToken ct)
    {
        foreach (var order in changes)
        {
            // Update customer order summary (different container)
            var summary = await GetOrCreateSummaryAsync(order.CustomerId, ct);

            summary.TotalOrders++;
            summary.TotalSpent += order.Total;
            summary.LastOrderDate = order.CreatedAt;

            await _summaryContainer.UpsertItemAsync(summary, new PartitionKey(summary.CustomerId), ct);
        }
    }
}
```

### Transactional Batch

```csharp
// All operations within same partition key
var batch = container.CreateTransactionalBatch(new PartitionKey(customerId));

batch.CreateItem(new OrderDocument { Id = orderId, CustomerId = customerId, ... });
batch.UpsertItem(new CustomerStatsDocument { Id = $"stats-{customerId}", TotalOrders = newTotal });
batch.PatchItem(inventoryId, new List<PatchOperation>
{
    PatchOperation.Decrement("/quantity", orderQuantity)
});

var response = await batch.ExecuteAsync();

if (!response.IsSuccessStatusCode)
{
    // Entire batch failed atomically
    throw new TransactionFailedException(response.StatusCode);
}
```

### Time-To-Live (TTL) Patterns

```csharp
// Container-level TTL
await database.CreateContainerIfNotExistsAsync(
    new ContainerProperties
    {
        Id = "sessions",
        PartitionKeyPath = "/userId",
        DefaultTimeToLive = 86400 // 24 hours in seconds
    });

// Document-level TTL (overrides container default)
var session = new SessionDocument
{
    Id = sessionId,
    UserId = userId,
    CreatedAt = DateTimeOffset.UtcNow,
    Ttl = 3600 // 1 hour - shorter than container default
};
```

---
[Back to Overview](./OVERVIEW.md)
