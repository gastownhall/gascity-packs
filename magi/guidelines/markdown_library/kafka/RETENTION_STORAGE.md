# Retention and Storage

### Retention Policies

| Policy | Property | Use For |
|:-------|:---------|:--------|
| Time-based | `retention.ms` (default 7 days) | Most event topics; replay window + compliance |
| Size-based | `retention.bytes` per partition | Capacity-constrained environments |
| Compact | `cleanup.policy=compact` | Changelog topics, state stores, entity snapshots |
| Compact + Delete | `cleanup.policy=compact,delete` | Compacted topics with eventual expiration |

### Segment Configuration

Kafka stores partitions as segments:

- `segment.bytes=1073741824` — segment size (1 GB default); smaller segments enable faster cleanup.
- `segment.ms=604800000` — force segment roll after duration (7 days default).
- The active segment is never deleted or compacted; roll to enable cleanup.

For compacted topics, smaller segments improve compaction latency but increase file handle usage.

### Storage Calculation

```text
daily_storage = messages_per_day × average_message_size × replication_factor
total_storage = daily_storage × retention_days
```

Add 20% overhead for segment metadata and indexing. Plan for peak throughput periods, not average.

### Tiered Storage (Kafka 3.6+)

```properties
remote.storage.enable=true
local.retention.ms=86400000          # 1 day hot
retention.ms=2592000000              # 30 days total
```

- Hot data on broker local disks.
- Cold data on remote object storage.
- Transparent to producers and consumers.
- Reduces broker storage costs for long retention.

Configure retention separately for local and remote tiers. Local retention affects read latency; remote retention affects cost and replay capability.

---
[Back to Overview](./OVERVIEW.md)
