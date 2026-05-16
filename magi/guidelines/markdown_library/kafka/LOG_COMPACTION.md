# Log Compaction

### Compacted Changelog

Maintain latest state per key:

```properties
cleanup.policy=compact
min.cleanable.dirty.ratio=0.5
segment.ms=86400000
delete.retention.ms=86400000
```

**Use cases:**

- Database changelog topics
- Cache invalidation
- Entity snapshots
- Configuration distribution

### Compact + Delete with Tombstones

```properties
cleanup.policy=compact,delete
retention.ms=604800000
```

**Tombstone handling:**

1. Send `null` value with key to delete.
2. Tombstone retained for `delete.retention.ms`.
3. Late consumers see deletion.

This combines compaction with eventual time-based expiration — keys can be deleted entirely rather than simply replaced.

---
[Back to Overview](./OVERVIEW.md)
