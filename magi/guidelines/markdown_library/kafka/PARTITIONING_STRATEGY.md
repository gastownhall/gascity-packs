# Partitioning Strategy

### Partition Fundamentals

Partitions are the unit of:

- **Parallelism** — maximum consumer instances equals partition count.
- **Ordering** — messages with the same key go to the same partition; ordering guaranteed only within a partition.
- **Storage** — each partition is a separate log on broker disks.
- **Replication** — each partition has a leader and replica set.

### Partition Count Selection

Starting partition count formula:

```text
max(expected_throughput_mb_per_sec / 10, expected_consumer_instances * 2)
```

Consider:

- Peak throughput requirements, not average.
- Consumer group parallelism needs.
- Future growth trajectory.
- Key cardinality for even distribution.

| Throughput Tier | Range | Partitions |
|:----------------|:------|:-----------|
| Low | < 1 MB/s | 6–12 |
| Medium | 1–50 MB/s | 12–50 |
| High | 50–200 MB/s | 50–200 |
| Very high | > 200 MB/s | 200+ with careful monitoring |

### Partition Key Selection

The partition key determines message distribution and ordering scope. Choose keys that:

- Distribute load evenly across partitions.
- Group related messages requiring ordering.
- Have high cardinality to prevent hot partitions.
- Remain stable for the entity's lifetime.

| Pattern | Example | Use For |
|:--------|:--------|:--------|
| Entity ID | `customer_id`, `order_id`, `device_id` | Entity-centric ordering |
| Tenant ID | `tenant_id` | Multi-tenant isolation |
| Composite | `{region}:{customer_id}` | Ordering scope narrower than entity |
| Null key | — | Round-robin when ordering irrelevant |

### Hot Partition Prevention

Hot partitions occur when key distribution is skewed. A single high-volume key sends all its messages to one partition, overwhelming one broker while others idle.

**Detection:**

- Monitor `BytesInPerSec` and `MessagesInPerSec` per partition.
- Alert when partition variance exceeds 2× average.
- Track partition lag distribution in consumer groups.

**Mitigation:**

- Add entropy to keys for high-volume entities: `{entity_id}:{random_suffix}`.
- Accept ordering loss for specific high-volume keys.
- Redesign key strategy to increase cardinality.
- Increase partition count (breaks existing key routing).

---
[Back to Overview](./OVERVIEW.md)
