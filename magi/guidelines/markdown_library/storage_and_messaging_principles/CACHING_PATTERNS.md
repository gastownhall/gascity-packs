# Caching Patterns

### Cache-Aside with Refresh-Ahead

```csharp
public class ProductCache
{
    private readonly IDistributedCache _cache;
    private readonly IProductRepository _repository;
    private readonly TimeSpan _ttl = TimeSpan.FromMinutes(10);
    private readonly TimeSpan _refreshThreshold = TimeSpan.FromMinutes(8);

    public async Task<Product> GetProductAsync(int productId, CancellationToken ct)
    {
        var cacheKey = $"product:{productId}";
        var cached = await _cache.GetAsync(cacheKey, ct);

        if (cached != null)
        {
            var entry = JsonSerializer.Deserialize<CacheEntry<Product>>(cached);

            // Refresh-ahead: async refresh if approaching expiration
            if (entry.CachedAt.Add(_refreshThreshold) < DateTimeOffset.UtcNow)
            {
                _ = RefreshCacheAsync(productId, cacheKey); // Fire and forget
            }

            return entry.Value;
        }

        // Cache miss: load from source
        var product = await _repository.GetByIdAsync(productId, ct);
        await CacheProductAsync(cacheKey, product, ct);
        return product;
    }

    private async Task RefreshCacheAsync(int productId, string cacheKey)
    {
        try
        {
            var product = await _repository.GetByIdAsync(productId, CancellationToken.None);
            await CacheProductAsync(cacheKey, product, CancellationToken.None);
        }
        catch (Exception ex)
        {
            // Log but don't fail; existing cache entry still valid
            _logger.LogWarning(ex, "Failed to refresh cache for product {ProductId}", productId);
        }
    }
}
```

### Cache Invalidation Strategies

**Time-Based (TTL)**:
- Simple, predictable
- Accept staleness window equal to TTL
- Works for reference data, configuration

**Event-Based**:
- Immediate invalidation on change
- Requires event infrastructure
- Use for frequently updated data

**Version-Based**:
- Include version in cache key: `product:123:v5`
- Increment version on update
- Old versions naturally expire
- Works for entities with version tracking

### Distributed Locking

```csharp
public class DistributedLock
{
    private readonly IDatabase _redis;
    private readonly string _lockKey;
    private readonly string _lockValue;
    private readonly TimeSpan _expiry;

    public async Task<bool> AcquireAsync()
    {
        // SET key value NX EX seconds
        return await _redis.StringSetAsync(
            _lockKey,
            _lockValue,
            _expiry,
            When.NotExists);
    }

    public async Task<bool> ReleaseAsync()
    {
        // Only release if we own the lock
        var script = @"
            if redis.call('get', KEYS[1]) == ARGV[1] then
                return redis.call('del', KEYS[1])
            else
                return 0
            end";

        var result = await _redis.ScriptEvaluateAsync(
            script,
            new RedisKey[] { _lockKey },
            new RedisValue[] { _lockValue });

        return (int)result == 1;
    }
}

// Usage
await using var lockHandle = await _lockManager.AcquireAsync("order:123:process", TimeSpan.FromMinutes(5));
if (lockHandle.Acquired)
{
    await ProcessOrder(orderId);
}
else
{
    // Another instance is processing; retry later or fail
}
```

---
[Back to Overview](./OVERVIEW.md)
