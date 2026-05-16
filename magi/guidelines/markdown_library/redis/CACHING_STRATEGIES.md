# Caching Strategies and Patterns

### Cache-Aside (Lazy Loading)

Application checks cache before querying data source. On cache miss, queries source and populates cache.

| Step | Action |
|:----:|:-------|
| 1 | Check cache for key |
| 2 | If present, return cached value |
| 3 | If absent, query data source |
| 4 | Store result in cache with TTL |
| 5 | Return value |

**Trade-offs:** demand-driven population; cache failure does not prevent data access; first request always hits data source (cold cache penalty); race condition possible on concurrent cache misses.

**Race-condition mitigation:** `SETNX` (SET if Not eXists) to prevent overwrite; accept last-write-wins for non-critical data; implement distributed locking for critical data (see §13).

### Write-Through

Every write to data source immediately writes to cache.

**Trade-offs:** cache always current; reads never hit cold cache for recently written data; write latency includes cache write; complex failure handling if cache write fails after database commit.

**Implementation:** wrap database and cache writes in application transaction; on cache write failure, **invalidate the key** rather than leaving stale data; consider async cache write for latency-sensitive paths.

### Write-Behind (Write-Back)

Writes go to cache immediately; persist to data source asynchronously.

**Trade-offs:** lowest write latency; batches database writes for efficiency; **data loss risk if cache fails before persistence**; complex consistency guarantees; not suitable for financial or compliance-critical data.

### Read-Through

Cache acts as the data access layer; application queries cache only.

**Trade-offs:** simplified application code; **Azure Cache for Redis does not support this natively** — requires application-side implementation. Less common in practice.

### Refresh-Ahead

Proactively refresh cache entries before expiration.

**Trade-offs:** eliminates cold-cache latency for popular keys; prevents thundering herd on expiration; complex implementation (tracking expiring keys, background refresh); wastes resources refreshing data that won't be read; suitable only for predictable, high-frequency access patterns.

---
[Back to Overview](./OVERVIEW.md)
