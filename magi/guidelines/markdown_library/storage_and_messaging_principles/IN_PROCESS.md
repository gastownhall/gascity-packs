# In-Process / In-Memory Solutions

### What They Are

In-process solutions store data in application memory without external dependencies. This includes language-native collections, caching libraries, and embedded databases.

### Types

**Native Collections**:
- Dictionary, List, HashSet, ConcurrentDictionary
- Fastest possible access; no serialization
- Lost on process restart; not shared across instances

**In-Memory Caching Libraries**:
- .NET MemoryCache, IMemoryCache
- Caffeine (Java), lru-cache (Node.js)
- TTL support, size limits, eviction policies

**Embedded Databases**:
- SQLite (relational, single-file)
- LiteDB (.NET document database)
- RocksDB (key-value, persistent)

**In-Process Message Passing**:
- System.Threading.Channels (.NET)
- BlockingCollection, ConcurrentQueue
- Actor frameworks (Akka.NET, Proto.Actor)

### Core Strengths

- **Zero Latency**: No network round-trip; measured in nanoseconds
- **No External Dependencies**: Simplifies deployment and testing
- **No Serialization Overhead**: Work directly with objects
- **Transactional with Application Code**: No distributed transaction concerns
- **Cost**: No additional service costs

### Core Weaknesses

- **Process Scope**: Data lost on restart; not shared across instances
- **Memory Bound**: Limited to process memory; impacts GC
- **No Durability**: Data exists only in process memory (unless using embedded DB)
- **No Horizontal Scaling**: Each instance has its own cache; cache coherence challenges
- **Cold Start**: Cache must be rebuilt on restart

### Ideal Use Cases

- Reference data that changes rarely and is read frequently
- Computed values that are expensive to recreate
- Single-instance applications or per-instance data
- Lookup tables loaded at startup
- Request-scoped caching
- Local queuing within a process

### Avoid When

- Data must survive process restart
- Data must be shared across multiple instances
- Memory pressure is a concern
- Cache coherence across instances is required
- Data size exceeds comfortable memory allocation

### IMemoryCache Pattern (.NET)

```csharp
public class ProductService
{
    private readonly IMemoryCache _cache;
    private readonly IProductRepository _repository;

    public async Task<Product> GetProductAsync(int productId)
    {
        var cacheKey = $"product:{productId}";

        if (!_cache.TryGetValue(cacheKey, out Product product))
        {
            product = await _repository.GetByIdAsync(productId);

            var options = new MemoryCacheEntryOptions()
                .SetAbsoluteExpiration(TimeSpan.FromMinutes(10))
                .SetSlidingExpiration(TimeSpan.FromMinutes(2))
                .SetSize(1); // For size-limited cache

            _cache.Set(cacheKey, product, options);
        }

        return product;
    }
}
```

### System.Threading.Channels (.NET)

```csharp
// Bounded channel for backpressure
var channel = Channel.CreateBounded<WorkItem>(new BoundedChannelOptions(1000)
{
    FullMode = BoundedChannelFullMode.Wait,
    SingleReader = true,
    SingleWriter = false
});

// Producer
await channel.Writer.WriteAsync(new WorkItem { /* ... */ });

// Consumer
await foreach (var item in channel.Reader.ReadAllAsync(cancellationToken))
{
    await ProcessWorkItem(item);
}
```

### SQLite for Local State

```csharp
// Embedded database for local persistence
using var connection = new SqliteConnection("Data Source=local.db");
connection.Open();

// Schema creation
connection.Execute(@"
    CREATE TABLE IF NOT EXISTS cache (
        key TEXT PRIMARY KEY,
        value BLOB,
        expires_at INTEGER
    )");

// Insert with expiration
connection.Execute(
    "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (@Key, @Value, @ExpiresAt)",
    new { Key = key, Value = serializedValue, ExpiresAt = DateTimeOffset.UtcNow.AddHours(1).ToUnixTimeSeconds() });
```

### When to Promote to External Service

Consider moving from in-process to external service when:
- Multiple instances need shared state
- Data must survive deployments/restarts
- Cache hit ratio is low due to instance-local caching
- Memory consumption impacts application performance
- Monitoring/observability of cached data is needed

---
[Back to Overview](./OVERVIEW.md)
