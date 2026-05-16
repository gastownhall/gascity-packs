# SDK Usage Patterns

### Client Initialization

Create one `CosmosClient` instance per application lifetime:
```csharp
var cosmosClient = new CosmosClient(
    connectionString,
    new CosmosClientOptions
    {
        ApplicationName = "OrderService",
        ConnectionMode = ConnectionMode.Direct,
        ConsistencyLevel = ConsistencyLevel.Session,
        MaxRetryAttemptsOnRateLimitedRequests = 9,
        MaxRetryWaitTimeOnRateLimitedRequests = TimeSpan.FromSeconds(30)
    });
```

**Do not create clients per request.** Connection establishment is expensive.

### Connection Mode

| Mode | Benefits | Drawbacks |
|:-----|:---------|:----------|
| **Direct** *(default)* | Lower latency, higher throughput | Requires outbound TCP ports 10250-10255 |
| Gateway | Firewall-friendly (port 443 only) | Higher latency; use only when network restrictions require |

### Point Operations

Point reads (by ID and partition key) are the most efficient operation:
```csharp
var response = await container.ReadItemAsync<Order>(orderId, new PartitionKey(tenantId));
var order = response.Resource;
var ruConsumed = response.RequestCharge;
```

Point reads cost approximately **1 RU for 1KB documents** regardless of container size.

### Upsert Pattern

Use upsert to create or replace without checking existence:
```csharp
var response = await container.UpsertItemAsync(order, new PartitionKey(order.TenantId));
```

Avoids read-then-write pattern that doubles RU cost and creates race conditions.

### Optimistic Concurrency

Use ETags to prevent lost updates:
```csharp
var options = new ItemRequestOptions { IfMatchEtag = order.ETag };
try
{
    await container.ReplaceItemAsync(order, order.Id, new PartitionKey(order.TenantId), options);
}
catch (CosmosException ex) when (ex.StatusCode == HttpStatusCode.PreconditionFailed)
{
    // Document was modified; reload and retry
}
```

### Bulk Operations

Use bulk execution for high-volume ingestion:
```csharp
var cosmosClient = new CosmosClient(connectionString,
    new CosmosClientOptions { AllowBulkExecution = true });

var tasks = orders.Select(order => container.CreateItemAsync(order, new PartitionKey(order.TenantId)));
await Task.WhenAll(tasks);
```

Bulk mode groups operations to the same partition for efficient batching.

### Transactional Batch

Atomic operations within a single partition:
```csharp
var batch = container.CreateTransactionalBatch(new PartitionKey(tenantId))
    .CreateItem(order)
    .CreateItem(orderEvent)
    .ReplaceItem(inventory.Id, updatedInventory);

var response = await batch.ExecuteAsync();
if (!response.IsSuccessStatusCode)
{
    // Entire batch failed atomically
}
```

All operations succeed or all fail. **Limited to single partition.** Up to 100 operations, max 2 MB total request size.

### Streaming for Large Results

Use `ToStreamAsync` for scenarios where deserialization overhead matters:
```csharp
var iterator = container.GetItemQueryStreamIterator(queryDefinition);
while (iterator.HasMoreResults)
{
    using var response = await iterator.ReadNextAsync();
    // Process response.Content stream directly
}
```

### Integrated Cache

Enable the integrated cache for read-heavy workloads:
- Reduces RU consumption for repeated reads
- Lower latency for cached data
- Automatic invalidation on writes
- Requires a dedicated gateway
- Configure cache size based on the working set

---
[Back to Overview](./OVERVIEW.md)
