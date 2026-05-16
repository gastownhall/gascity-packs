# Redundancy and SnapshotStateProvider

| Aspect | 8.1 | 8.3 |
|:-------|:----|:----|
| Runtime state interface | `RuntimeStateProvider` | **`SnapshotStateProvider`** |
| Methods | `getRuntimeState` / `setRuntimeState` | `takeSnapshot()` / `restoreSnapshot(byte[])` |

```java
context.getRedundancyManager().registerRuntimeStateProvider(snapshotStateProvider);
```

| Use For | Do Not Use For |
|:--------|:---------------|
| Alarm acknowledgment state | Configuration (use resource collections) |
| In-flight transaction IDs | Historical data (use `HistoryManager`) |
| Sequence counters | Transient caches (recreate on startup) |
| Accumulated statistics | — |

---
[Back to Overview](./OVERVIEW.md)
