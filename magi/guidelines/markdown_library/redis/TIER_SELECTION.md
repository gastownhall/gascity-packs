# Tier Selection and Architecture

### Azure Cache for Redis Tiers

| Tier | Use case | Key features | Limits |
|:-----|:---------|:-------------|:-------|
| Basic | **Dev/test only** | Single node, no replication, no SLA | 53GB max; cache loss on restart |
| Standard | Production with SLA | Primary/replica with auto-failover; 99.9% SLA | 53GB max; no clustering |
| Premium | Production at scale | Clustering, VNet, geo-replication (active-passive), RDB persistence, zone redundancy | 1.2TB (10 shards × 120GB) |
| Enterprise | Modules + active-active | Redis Modules; active-active geo with CRDTs; 99.999% SLA | 2TB per cluster |
| Enterprise Flash | Cost-optimized large datasets | Flash storage option | 13TB+ |

### Tier Selection Decision Matrix

| Requirement | Minimum Tier |
|:------------|:-------------|
| Development / testing | Basic |
| Production with SLA | Standard |
| Clustering (>53GB or distributed load) | Premium |
| VNet integration | Premium |
| Geo-replication (active-passive) | Premium |
| Active-active geo-replication | Enterprise |
| Redis Modules (RediSearch, etc.) | Enterprise |
| 99.999% SLA requirement | Enterprise |
| Flash storage (cost-optimized large datasets) | Enterprise Flash |

### Sizing Considerations

**Memory sizing:**

- Start with 2× estimated dataset size to account for fragmentation and overhead.
- Hash, list, and sorted-set structures have per-element overhead — factor 20–30% overhead for complex structures.
- Leave **25% headroom** for key growth, temporary spikes, and replication buffer.

**Connection limits:**

| Tier | Connection range |
|:-----|:-----------------|
| Basic / Standard | 256 to 20,000 (depending on cache size) |
| Premium | 7,500 to 40,000 (depending on size and shards) |
| Enterprise | Higher; check documentation for specific SKU |

**Network bandwidth:** each tier has bandwidth limits that throttle operations when exceeded. High-throughput workloads (bulk operations, large values) can hit bandwidth before hitting CPU or memory. Monitor the cache server load metric — spikes indicate bandwidth saturation.

### Architecture Patterns

| Pattern | When to use |
|:--------|:------------|
| Single cache for multiple applications | Apps share a trust boundary and eviction policy; use database numbers (0–15) or key prefixes for logical separation |
| Cache per application | Stronger isolation; one app cannot affect another; higher total cost; required for compliance |
| Shared cache with Premium clustering | Hash tags route related keys to the same shard; monitor for uneven distribution and hot shards |

---
[Back to Overview](./OVERVIEW.md)
