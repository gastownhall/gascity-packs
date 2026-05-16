# Consumer Group Management

### Group Coordinator

The group coordinator is a broker responsible for:

- Managing group membership.
- Handling consumer heartbeats.
- Orchestrating rebalances.
- Storing committed offsets.

Each group has one coordinator determined by hashing group ID to `__consumer_offsets` partition.

### Assignment Strategies

| Strategy | Description | Trade-off |
|:---------|:------------|:----------|
| Range | Per-topic contiguous ranges | Imbalance when partition count is not divisible by consumer count |
| RoundRobin | Even distribution across consumers | Partitions from same topic may scatter |
| Sticky | Minimizes movement during rebalance | Maintains previous assignments when possible |
| **CooperativeStickyAssignor** (recommended) | Sticky + incremental rebalancing | Only revokes partitions being reassigned, not all |

```properties
partition.assignment.strategy=org.apache.kafka.clients.consumer.CooperativeStickyAssignor
```

### Static Membership

Configure `group.instance.id` for stable consumer identity:

- Rejoin within `session.timeout.ms` without triggering rebalance.
- Useful for rolling restarts.
- Reduces rebalance frequency in container environments.

**Trade-off**: longer detection time for genuine failures. Session timeout must be longer than restart duration.

### Offset Management

Offsets stored in `__consumer_offsets` topic:

- 50 partitions by default.
- Replicated for durability.
- Compacted to retain only latest offset per group/topic/partition.

**Monitor consumer lag:**

- `records-lag-max` — maximum lag across assigned partitions.
- Lag increasing over time → consumer falling behind.
- Lag spikes during deployments are normal; sustained lag is not.

---
[Back to Overview](./OVERVIEW.md)
