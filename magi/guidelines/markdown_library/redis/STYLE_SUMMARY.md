# Style Summary

| Element | Required Style |
|:--------|:---------------|
| Tier Selection | Production requires Standard minimum; Premium for clustering/VNet; Enterprise for modules |
| Key Naming | `{namespace}:{entity}:{identifier}` with lowercase and colon separators |
| TTL | Required on all cached data; no infinite-TTL cache entries |
| Connections | Pooled and reused; single `ConnectionMultiplexer` per endpoint in .NET |
| Serialization | MessagePack/Protobuf for performance; JSON for debuggability; always versioned |
| Multi-Key Operations | Hash tags for related keys in clusters; accept single-slot constraint |
| Client-Side Cache | Enable for hot keys with proper invalidation; TTL shorter than server TTL |
| Session Storage | Redis for distributed sessions; hash type for partial updates |
| Pub/Sub | At-most-once delivery; use Streams for guaranteed delivery |
| Eviction Policy | `allkeys-lru` default; choose based on access pattern |
| Memory | 25% headroom minimum; monitor fragmentation ratio |
| Security | TLS required; VNet or private endpoint; rotate keys |
| Persistence | RDB for Premium when warm-up matters; understand data loss window |
| Pipelining | Batch independent commands; 100–1000 per pipeline |
| Distributed Locks | Unique identifier; TTL mandatory; Lua check-and-delete |
| Rate Limiting | Sliding window or token bucket via Lua; match TTL to window |
| Cache Stampede | Probabilistic early refresh or single-flight regeneration lock |
| Sentinel | Minimum 3 instances, odd count, separate failure zones |
| Monitoring | Server load, memory, connections, evictions; alert on thresholds |
| Shared Instances | Key prefix isolation; monitor per-namespace usage |
| Multi-Tier Caching | L1 in-process with short TTL; L2 Redis with longer TTL |
| Failover Handling | Retry with backoff; circuit breaker; fallback to data source |
| Cost | Right-size based on actual usage; reserved capacity for stable workloads |
| Shakedown | Per-primitive canary round-trip via real pool; pass / fail-blocking / fail-nonblocking / inconclusive |
| Defense in Depth | Persistence + replication/cluster + monitoring + retries + stampede protection + offsite backups + schema discipline |
| Rule of Three | Three Sentinels (or three Cluster masters) MUST agree before a failover decision |

---
[Back to Overview](./OVERVIEW.md)
