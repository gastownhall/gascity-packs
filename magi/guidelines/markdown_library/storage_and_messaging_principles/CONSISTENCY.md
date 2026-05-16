# Consistency Considerations

### CAP Theorem Refresher

In a distributed system, you can have at most two of three:
- **Consistency**: Every read receives the most recent write
- **Availability**: Every request receives a response
- **Partition Tolerance**: System continues operating despite network partitions

Since network partitions are inevitable, the real choice is between consistency and availability during partitions.

### Technology Consistency Characteristics

| Technology     | Default Consistency  | Configurable                |
|----------------|----------------------|-----------------------------|
| SQL Server     | Strong               | Limited (isolation levels)  |
| PostgreSQL     | Strong               | Limited (isolation levels)  |
| Cosmos DB      | Session              | Yes (5 levels)              |
| Redis          | Eventual (cluster)   | No (strong for single node) |
| Blob Storage   | Strong (single blob) | No                          |
| Storage Queues | Eventual             | No                          |
| RabbitMQ       | Strong (single node) | Limited                     |

### Designing for Eventual Consistency

When using eventually consistent systems:

1. **Idempotent Operations**: Design so repeating an operation has same effect
2. **Conflict Resolution**: Define how to resolve concurrent updates
3. **Compensation**: Plan for rolling back partially completed distributed operations
4. **Staleness Tolerance**: Understand and document acceptable staleness
5. **Monotonic Reads**: Ensure users don't see older data after seeing newer
6. **Causal Consistency**: Ensure related operations appear in correct order

### CP Pattern — Consistency + Partition Tolerance

System remains consistent but may become unavailable during network partitions. Suitable for **financial transactions, inventory management, configuration management**.

```csharp
// CP Pattern: Bank transfer must be consistent
public async Task TransferFundsAsync(decimal amount, string fromAccount, string toAccount)
{
    using var transaction = await _db.BeginTransactionAsync(IsolationLevel.Serializable);
    // This will fail if partition occurs (choosing consistency over availability)
    var from = await _db.Accounts.LockForUpdate(fromAccount);
    var to = await _db.Accounts.LockForUpdate(toAccount);
    if (from.Balance < amount)
        throw new InsufficientFundsException();
    from.Balance -= amount;
    to.Balance += amount;
    await transaction.CommitAsync(); // Fails if can't reach quorum
}
```

CP technologies: SQL Server with synchronous replication, MongoDB with majority writes, HBase, Zookeeper.

### AP Pattern — Availability + Partition Tolerance

System remains available but may serve inconsistent data during partitions. Suitable for **social media feeds, product catalogs, user preferences, shopping carts**.

```csharp
// AP Pattern: Shopping cart remains available even if inconsistent
public async Task AddToCartAsync(string userId, CartItem item)
{
    try
    {
        // Write to primary region
        await _primaryRegion.AddToCartAsync(userId, item);
    }
    catch (PartitionException)
    {
        // During partition, write to local region (may cause inconsistency)
        await _localRegion.AddToCartAsync(userId, item);
        // Queue for reconciliation when partition heals
        await _reconciliationQueue.EnqueueAsync(new CartUpdate(userId, item));
    }
}
```

AP technologies: Cosmos DB with eventual consistency, Cassandra, DynamoDB, CouchDB.

### Tunable Consistency

Allow different consistency levels for different operations on the same store:

```csharp
// Cosmos DB with per-operation consistency
public class ProductService
{
    // Strong consistency for price updates
    public async Task UpdatePriceAsync(string productId, decimal newPrice)
    {
        var options = new ItemRequestOptions
        {
            ConsistencyLevel = ConsistencyLevel.Strong
        };
        await _container.UpsertItemAsync(product, options);
    }
    // Eventual consistency for view counts
    public async Task IncrementViewCountAsync(string productId)
    {
        var options = new ItemRequestOptions
        {
            ConsistencyLevel = ConsistencyLevel.Eventual
        };
        await _container.PatchItemAsync(productId, patches, options);
    }
}
```

---
[Back to Overview](./OVERVIEW.md)
