# Integration with Application Caching Layers

### Multi-Tier Caching Architecture

| Tier | Latency | Scope | Size |
|:-----|:--------|:------|:-----|
| L1 — In-process memory cache (`IMemoryCache`, Guava, LRU) | Microseconds | Single instance | App heap limited |
| L2 — Distributed cache (Redis) | Single milliseconds | All instances | Cache tier sized |
| L3 — Data source (database, API) | 10–100+ ms | Authoritative | Full dataset |

### Cache Access Pattern

```text
Read request arrives
├─ Check L1 (local cache)
│  ├─ Hit → Return immediately
│  └─ Miss → Check L2 (Redis)
│     ├─ Hit → Populate L1, return
│     └─ Miss → Query data source
│        └─ Populate L2 and L1, return
```

### Invalidation Coordination

Challenge: L1 caches on different instances become stale when data changes.

| Approach | Behavior |
|:---------|:---------|
| Pub/Sub invalidation | Writer publishes; all instances evict from L1; next L1 miss loads fresh from L2 |
| Time-based invalidation | L1 TTL 10–60s (accept brief staleness); L2 TTL longer; simpler, less immediate consistency |

### ASP.NET Core Integration

```csharp
// IDistributedCache with Microsoft.Extensions.Caching.StackExchangeRedis
services.AddStackExchangeRedisCache(options =>
{
    options.Configuration = builder.Configuration.GetConnectionString("Redis");
    options.InstanceName = "MyApp";
});
```

| Component | Description |
|:----------|:------------|
| `IDistributedCache` | Standard interface; `Microsoft.Extensions.Caching.StackExchangeRedis` provides Redis impl; serializes to byte array |
| `HybridCache` (.NET 9+) | Built-in two-tier caching; automatic L1/L2 coordination; stampede protection (single-flight); tag-based invalidation |
| Output caching | `AddStackExchangeRedisOutputCache` — distributed HTTP response cache; varies by route, query, headers |

### Spring Framework Integration

```java
@Configuration
@EnableRedisHttpSession(maxInactiveIntervalInSeconds = 1800)
public class RedisSessionConfig {
    @Bean
    public LettuceConnectionFactory connectionFactory() {
        return new LettuceConnectionFactory(
            new RedisStandaloneConfiguration("redis.example.com", 6379)
        );
    }
}
```

### Application Resilience

| Scenario | Handling |
|:---------|:---------|
| Cache failure | Circuit breaker; serve from data source directly; graceful degradation |
| Startup without Redis | Application starts even if Redis unavailable; log warning; operate with L1-only or no caching; reconnect when Redis becomes available |

---
[Back to Overview](./OVERVIEW.md)
