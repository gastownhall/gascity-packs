# Data Modeling and Key Design

### Key Naming Conventions

Redis keys are arbitrary byte sequences, but disciplined naming is essential for operational clarity.

**Structure:** `{namespace}:{entity}:{identifier}:{attribute}`

Examples:

- `user:12345:profile`
- `session:abc123def456`
- `cart:user:12345:items`
- `cache:product:sku:789:details`
- `ratelimit:api:user:12345:minute`

**Rules:**

- Use colons (`:`) as hierarchy separators — universally recognized convention.
- Lowercase all key components.
- Include type or namespace prefix to identify data category.
- Keep keys under **1KB**; shorter keys reduce memory and improve performance.
- **Never include sensitive data (PII, secrets) in key names** — keys appear in logs and monitoring.

### Hash Tags for Clustering

In clustered Redis, keys hash to slots (0–16383) determining which shard stores the key. Related keys may land on different shards, preventing multi-key operations.

Hash tags force related keys to the same slot:

```text
{user:12345}:profile
{user:12345}:preferences
{user:12345}:settings
```

Only the content within `{}` is hashed. Enables transactions, Lua scripts, and `MGET`/`MSET` across related keys.

| Use hash tags when | Avoid hash tags when |
|:-------------------|:---------------------|
| Multiple keys must be updated atomically | They would create hot shards (all keys for popular entity on one node) |
| Lua scripts operate on multiple keys | Keys are naturally independent and don't require multi-key operations |
| Pipeline operations require key colocality | — |

### Data Structure Selection

| Structure | Use for | Operations | Notes |
|:----------|:--------|:-----------|:------|
| Strings | Cached responses, session tokens, counters, distributed locks | `GET`, `SET`, `INCR`, `APPEND`, TTL | Most efficient for single values under 44 bytes (embedded string optimization) |
| Hashes | User profiles, configuration objects, partial updates | `HGET`, `HSET`, `HMGET`, `HINCRBY`, `HDEL` | Don't exceed tens of thousands of fields per hash |
| Lists | Message queues, activity feeds, bounded logs | `LPUSH`, `RPOP`, `LRANGE`, `LTRIM` | Random access by index in large lists is O(n) |
| Sets | Tags, unique tracking, set intersection/union | `SADD`, `SISMEMBER`, `SINTER`, `SUNION`, `SCARD` | Each member has overhead — not suitable for millions of small elements |
| Sorted Sets | Leaderboards, priority queues, time-series indices, range queries | `ZADD`, `ZRANGE`, `ZRANGEBYSCORE`, `ZRANK`, `ZINCRBY` | 64-bit float scores; logarithmic operations; scales to millions |
| Streams | Event sourcing, message queues with ack, activity logs | `XADD`, `XREAD`, `XREADGROUP`, `XACK`, `XTRIM` | Consumer groups provide exactly-once semantics within Redis |

**Bound the work.** Use `LTRIM` to cap list size after push for bounded collections. Use `XTRIM stream MAXLEN ~ 10000` to cap stream size (approximate for performance).

### Value Serialization

| Format | Suitable for | Overhead | Notes |
|:-------|:-------------|:---------|:------|
| JSON | Cached API responses, configuration, debug-friendly data | 2–3× larger than binary | Use RedisJSON module for native JSON ops (Enterprise) |
| MessagePack / Protocol Buffers | High-throughput caching, bandwidth-sensitive scenarios | 20–50% smaller than JSON; faster | Requires schema coordination |
| Raw bytes / strings | Simple strings, pre-serialized data, binary blobs | Zero | Directly store what you retrieve |

### TTL Strategy

**Every cached value must have a TTL.** Infinite TTL keys accumulate and cause memory pressure.

| Strategy | Description | Use when |
|:---------|:------------|:---------|
| Absolute expiration | Set TTL at write time | Data has known staleness tolerance |
| Sliding expiration | Extend TTL on each access | Frequently accessed data should stay warm |
| Lazy expiration | Let Redis evict naturally based on memory pressure | Data is truly expendable; only with proper eviction policy |

```text
# Absolute
SET key value EX 3600

# Sliding (pipeline)
GET key
EXPIRE key 3600
```

**TTL guidelines by data type:**

| Data type | TTL |
|:----------|:----|
| Session data | Minutes to hours based on session timeout policy |
| Cached database queries | Seconds to minutes based on staleness tolerance |
| Cached API responses | Based on upstream cache headers or business rules |
| Rate limit counters | Match the rate limit window exactly |
| Distributed locks | Short TTL (seconds) with refresh; prevents deadlocks |

---
[Back to Overview](./OVERVIEW.md)
