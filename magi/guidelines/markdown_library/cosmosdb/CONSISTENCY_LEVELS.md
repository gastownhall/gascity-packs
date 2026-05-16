# Consistency Levels

### Consistency Spectrum

Cosmos DB offers five consistency levels, from strongest to weakest:

| Level | Guarantees | Notes |
|:------|:-----------|:------|
| **Strong** | Linearizability; reads return most recent committed write | Single write region only; highest latency and RU cost |
| **Bounded Staleness** | Reads lag by at most K versions or T seconds; linearizable within bound | Global apps needing strong-ish consistency |
| **Session** *(default)* | Read-your-writes within session; monotonic reads/writes | User-facing apps |
| **Consistent Prefix** | Never see out-of-order writes | No staleness guarantees |
| **Eventual** | No ordering guarantees | Lowest latency and RU cost |

### Default Consistency

Set account-level default consistency. Operations can request **weaker** consistency but never stronger:
- Account default: Session
- Request override: Eventual (allowed, weaker)
- Request override: Strong (rejected if account default is Session)

### Consistency Selection

| Use case | Recommended level |
|:---------|:------------------|
| Financial transactions; distributed locking | Strong |
| Global apps with predictable staleness; reporting | Bounded Staleness |
| User-facing apps; shopping carts; profiles; dashboards | **Session (default)** |
| Event streaming; audit logs requiring sequence | Consistent Prefix |
| Analytics; aggregations; high-throughput ingestion | Eventual |

### Consistency and Multi-Region

- **Strong** consistency with multi-region writes: **Not available**
- **Strong** consistency with single write region: Reads from any region wait for replication
- **Session** consistency with multi-region: Session tokens must be propagated between clients reading from different regions

---
[Back to Overview](./OVERVIEW.md)
