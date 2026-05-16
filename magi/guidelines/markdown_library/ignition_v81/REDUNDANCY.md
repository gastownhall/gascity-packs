# Redundancy

Active/backup Gateway pair behavior.

| Concern | Behavior |
|:--------|:---------|
| Configuration sync | Internal database (PersistentRecord) replicates active→backup automatically. Modules generally do not need manual sync code |
| State change events | `RedundancyManager.addStateListener` for state-change notifications. Adjust behavior per Active/Warm/Cold state |
| Operational state | `RuntimeStateProvider` for state that should transfer on failover (alarm ack state, in-flight transactions, sequence counters). **Replaced in 8.3 by `SnapshotStateProvider`** |

---
[Back to Overview](./OVERVIEW.md)
