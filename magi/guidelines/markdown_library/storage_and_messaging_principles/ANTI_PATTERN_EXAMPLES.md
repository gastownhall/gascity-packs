# Anti-Pattern Code Examples

### Wrong Consistency Level for Use Case

```csharp
// WRONG: Using eventual consistency for financial transactions
public async Task TransferMoneyAsync(decimal amount, string from, string to)
{
    // This could result in double-spending!
    var options = new RequestOptions { ConsistencyLevel = ConsistencyLevel.Eventual };
    var fromAccount = await _cosmos.ReadItemAsync(from, options);
    fromAccount.Balance -= amount;
    await _cosmos.UpsertItemAsync(fromAccount, options);
    var toAccount = await _cosmos.ReadItemAsync(to, options);
    toAccount.Balance += amount;
    await _cosmos.UpsertItemAsync(toAccount, options);
}

// CORRECT: Use strong consistency or transactional batch
public async Task TransferMoneyAsync(decimal amount, string from, string to)
{
    using var batch = _cosmos.CreateTransactionalBatch(partitionKey);
    batch.PatchItem(from, new[]
    {
        PatchOperation.Decrement("/balance", amount),
        PatchOperation.Add("/transactions/-", transactionRecord)
    });
    batch.PatchItem(to, new[]
    {
        PatchOperation.Increment("/balance", amount),
        PatchOperation.Add("/transactions/-", transactionRecord)
    });
    var response = await batch.ExecuteAsync();
    if (!response.IsSuccessStatusCode)
        throw new TransferFailedException();
}
```

### Ignoring Cost Implications

```csharp
// WRONG: Storing years of logs in premium Redis (expensive per GB, no expiration)
public class LogStorage
{
    private readonly IDatabase _redis;
    public async Task StoreLogAsync(LogEntry entry)
    {
        var key = $"log:{entry.Timestamp:yyyyMMddHHmmss}";
        await _redis.StringSetAsync(key, JsonSerializer.Serialize(entry));
        // No expiration = permanent storage in expensive Redis
    }
}

// CORRECT: Tier storage by access pattern — hot in Redis with short TTL, archive in blob
public class LogStorage
{
    public async Task StoreLogAsync(LogEntry entry)
    {
        // Recent logs in Redis for quick access
        if (entry.Timestamp > DateTimeOffset.UtcNow.AddHours(-24))
        {
            var key = $"log:{entry.Timestamp:yyyyMMddHHmmss}";
            await _redis.StringSetAsync(key, JsonSerializer.Serialize(entry),
                expiry: TimeSpan.FromDays(1));
        }
        // All logs to cheap blob storage
        var blobName = $"logs/{entry.Timestamp:yyyy/MM/dd}/{entry.Id}.json";
        await _blobClient.UploadAsync(new BinaryData(entry));
    }
}
```

---
[Back to Overview](./OVERVIEW.md)
