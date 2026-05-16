# Memory Management and Eviction

### Memory Architecture

**Used memory components:** data (keys + values), overhead (per-key/value metadata, hash table entries), fragmentation (allocator overhead, freed space not returned to OS), replication buffers (data queued for replica sync), client buffers (output buffers for slow clients).

### Memory Metrics

| Metric | Meaning |
|:-------|:--------|
| `usedmemory` | Actual bytes used by Redis |
| `usedmemory_rss` | Memory as seen by OS (includes fragmentation) |
| `mem_fragmentation_ratio` | RSS / `used_memory` (>1.5 indicates fragmentation) |
| `maxmemory` | Configured limit |
| `evicted_keys` | Keys removed due to memory pressure |

### Eviction Policies

When memory reaches `maxmemory`, Redis applies eviction policy:

| Policy | Behavior | Use when |
|:-------|:---------|:---------|
| `noeviction` | Return errors for writes; reads continue (default) | Cache overflow is critical and requires investigation |
| `allkeys-lru` | Evict LRU keys across all keys | **Recommended default for general-purpose caching** |
| `volatile-lru` | Evict LRU keys with TTL set only | Some keys are permanent; evict only expiring keys |
| `allkeys-random` | Evict random keys | Access pattern is uniform; LRU overhead undesirable |
| `volatile-random` | Evict random keys with TTL | Combination of random eviction and TTL filtering |
| `volatile-ttl` | Evict keys with shortest TTL first | Short-TTL data is most expendable |
| `allkeys-lfu` | Evict LFU keys (Redis 4.0+) | Frequency matters more than recency; "heavy hitters" workloads |
| `volatile-lfu` | LFU eviction for keys with TTL only | — |

### Memory Optimization

- **Key expiration** — TTL on all expendable keys.
- **Small values** — compress large values before storage; store IDs not full objects.
- **Hash optimization** — `hash-max-ziplist-entries` (512) and `hash-max-ziplist-value` (64) control compact encoding. Up to 10× memory reduction for small hashes.
- **Integer encoding** — `SET user:12345:age 25` is more memory-efficient than `SET user:12345:age "25"`.
- **Shared objects** — Redis shares common integer objects (0–9999); no additional memory for common integer values.
- **Scan for large keys** — identify memory hogs with `MEMORY USAGE`, `MEMORY STATS`, `MEMORY DOCTOR`, `DEBUG OBJECT`.

### Find Top Memory Consumers

```bash
#!/bin/bash
# Find top 100 largest keys; sort and report top 20
redis-cli --scan --pattern '*' | head -100 | while read key; do
    echo "$(redis-cli MEMORY USAGE "$key") $key"
done | sort -rn | head -20
```

### Handling Memory Pressure

| Symptom | Response |
|:--------|:---------|
| Eviction count increasing | Short-term: increase cache size |
| Write failures with `OOM` errors | Medium-term: reduce TTL to expire data faster |
| High server load metric | Long-term: optimize data model, split across multiple caches |

---
[Back to Overview](./OVERVIEW.md)
