# Change Feed Processing

### Change Feed Fundamentals

The Change Feed is an ordered log of all inserts and updates within a container:
- **Deletes are not captured** (use soft delete with TTL if needed)
- Changes ordered by modification time within each partition
- No cross-partition ordering guarantees
- Infinite retention in change feed (reads limited by data retention)

### Use Cases

- Event-driven architectures: react to data changes
- Materialized views: maintain denormalized aggregates
- Data synchronization: replicate to other data stores
- Audit logging: capture all changes for compliance
- Real-time analytics: stream to analytics pipelines

### Change Feed Processor

```csharp
var processor = container.GetChangeFeedProcessorBuilder<Order>("processorName", HandleChangesAsync)
    .WithInstanceName("instance1")
    .WithLeaseContainer(leaseContainer)
    .WithStartTime(DateTime.UtcNow.AddHours(-1))
    .Build();

await processor.StartAsync();
```

The processor:
- Manages partition distribution across instances
- Tracks progress with lease documents
- Handles instance failures with automatic rebalancing
- Checkpoints after successful processing

### Handler Implementation

```csharp
async Task HandleChangesAsync(IReadOnlyCollection<Order> changes, CancellationToken cancellationToken)
{
    foreach (var order in changes)
    {
        await ProcessOrderChange(order);
    }
    // Checkpoint happens after this returns without exception
}
```

**Process changes idempotently** — the handler may receive the same change on retry after failures.

### Lease Container

- Dedicated container for lease documents
- Same partition key as source container not required
- Provision adequate RU/s based on processor instance count and throughput
- One lease document per physical partition of source container

### Azure Functions Integration

```csharp
[FunctionName("ProcessOrderChanges")]
public async Task Run(
    [CosmosDBTrigger(
        databaseName: "orders-db",
        containerName: "orders",
        Connection = "CosmosDbConnection",
        LeaseContainerName = "leases",
        CreateLeaseContainerIfNotExists = true)] IReadOnlyList<Order> changes)
{
    foreach (var order in changes)
    {
        await ProcessOrder(order);
    }
}
```

---
[Back to Overview](./OVERVIEW.md)
