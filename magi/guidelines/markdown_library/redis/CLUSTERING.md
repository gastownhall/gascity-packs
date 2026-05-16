# Clustering and Sharding

### Azure Cache for Redis Clustering

Premium and Enterprise tiers support clustering:

- Data partitioned across shards (1–10 shards for Premium).
- Each shard is primary/replica pair.
- Keys hashed to slots (0–16383): `CRC16(key) mod 16384`.
- Slot assigned to shard deterministically.

**Client behavior:** client sends command to any node; if key on different node, receives `MOVED` redirect; client caches slot mappings; future commands route directly. Cluster-aware clients handle redirection transparently.

### Hash Slot Distribution

- **Even distribution** — random key distribution spreads load across shards.
- **Hotspot risk** — certain key patterns concentrate on single shard.

**Identifying hot shards:**

- Monitor per-shard CPU and memory metrics.
- High CPU on one shard with others idle indicates hotspot.
- Redistribute keys or split hot entities across multiple keys.

### Multi-Key Operations in Clusters

Multi-key commands require all keys on same slot. Affected commands: `MGET`, `MSET`, `DEL` with multiple keys, `PFMERGE`, set operations (`SUNION`, `SINTER`).

**Error on cross-slot:** `CROSSSLOT Keys in request don't hash to the same slot`.

| Solution | When |
|:---------|:-----|
| Hash tags | Use `{user:123}:profile`, `{user:123}:prefs` |
| Split operations | Multiple single-key operations in pipeline |
| Redesign | Restructure to not require multi-key atomicity |

### Transactions in Clusters

`MULTI`/`EXEC` transactions work within a single slot. All keys in transaction must hash to same slot. Use hash tags for transaction participants. Lua scripts have the same single-slot constraint.

### Scaling Clusters

| Operation | Behavior |
|:----------|:---------|
| Scale up (larger nodes) | Change cache size in Azure Portal; brief failover during resize; no data loss |
| Scale out (more shards) | Add shards; slots rebalanced automatically; some latency during rebalancing — plan for off-peak |
| Scale down | Reduce shard count; slots consolidated; **risk of OOM if not sized correctly** |

---
[Back to Overview](./OVERVIEW.md)
