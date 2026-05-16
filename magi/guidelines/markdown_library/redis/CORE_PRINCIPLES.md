# Core Principles

These guidelines define strict, performant, and operationally sound patterns for Redis deployments on Azure Cache for Redis, optimizing for:

- **Latency Minimization** — Every microsecond matters in caching; network hops, serialization overhead, and connection establishment are first-order concerns that compound at scale.
- **Memory Efficiency** — Redis operates entirely in memory; every byte stored has direct cost implications and affects eviction behavior under pressure.
- **Connection Discipline** — Redis connections are expensive resources with hard limits; multiplexing, pooling, and connection lifecycle management are non-negotiable.
- **Consistency Awareness** — Redis is not a database; applications must tolerate cache misses, handle stale data gracefully, and never treat Redis as the source of truth for critical data.
- **Failure Resilience** — Caches fail, networks partition, and nodes restart; applications must degrade gracefully without Redis rather than fail catastrophically.

### Primary Rule: Redis Is Ephemeral by Design

Redis is a cache and in-memory data store, **not a durable database**. Data in Redis can disappear due to eviction, restart, failover, or memory pressure. Applications must function correctly when Redis is unavailable or returns cache misses. Any design that treats Redis as the authoritative data store for non-recoverable data is fundamentally broken.

```python
# WRONG: Treating Redis as primary data store
user = redis.get(f"user:{user_id}")
if not user:
    return "User not found", 404  # Assumes Redis is authoritative
```

```python
# CORRECT: Redis as cache with fallback
user = redis.get(f"user:{user_id}")
if not user:
    user = database.get_user(user_id)  # Fallback to source
    if user:
        redis.set(f"user:{user_id}", user, ex=3600)
return user
```

### Secondary Rule: Measure Latency at the Application Layer

Redis operations execute in microseconds on the server. The latency your application experiences includes network round-trip time, serialization, connection acquisition, and client-side processing. **Benchmark from the application's perspective, not Redis's `INFO` statistics.** A 0.1ms Redis operation becomes 5ms when your application establishes a new connection for each request.

### Azure Cache for Redis Context

Azure Cache for Redis provides managed Redis instances with Azure-specific capabilities:

- **Managed infrastructure**: patching, failover, scaling handled by Azure.
- **Network integration**: VNet injection, Private Link, firewall rules.
- **Geo-replication**: cross-region active-passive replication (Premium and Enterprise).
- **Clustering**: automatic sharding across nodes (Premium and Enterprise).
- **Enterprise features**: Redis Modules (RediSearch, RedisJSON, RedisBloom, RedisTimeSeries).

These guidelines assume Azure Cache for Redis unless explicitly discussing self-managed Redis. Concepts apply broadly to Redis deployments, but operational procedures and configuration paths differ in self-managed environments.

### When Redis Fits

| Use Redis | Use alternatives |
|:----------|:-----------------|
| Sub-millisecond latency required | CDN or simpler caches for plain key-value |
| Rich data structures (sorted sets, streams, hashes) provide value | Database for persistent storage |
| Pub/Sub or real-time messaging needed alongside caching | In-process caches for object caching within a single process |
| Session storage requires atomic operations and expiration | Blob storage or database for massive datasets with infrequent access |
| Distributed locking or rate limiting requires atomic primitives | — |

---
[Back to Overview](./OVERVIEW.md)
