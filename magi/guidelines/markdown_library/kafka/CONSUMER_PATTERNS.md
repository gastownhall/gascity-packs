# Consumer Patterns

### Consumer Configuration

**Group coordination:**

| Property | Default / Required |
|:---------|:-------------------|
| `group.id` | Required — consumers with same ID share partitions |
| `group.instance.id` | Static membership to reduce rebalances on restart |
| `session.timeout.ms` | `45000` |
| `heartbeat.interval.ms` | `15000` (≈ 1/3 of session timeout) |

**Offset management:**

| Property | Value | Purpose |
|:---------|:------|:--------|
| `enable.auto.commit` | `false` | Manual commits for exactly-once processing |
| `auto.offset.reset` | `earliest` (replay) or `latest` (real-time only) | Behavior on new group |

**Fetching:**

| Property | Value |
|:---------|:------|
| `fetch.min.bytes` | `1` (increase for throughput) |
| `fetch.max.wait.ms` | `500` |
| `max.poll.records` | `500` (tune based on processing time) |
| `max.poll.interval.ms` | `300000` |

### Poll Loop Design

The consumer poll loop is the heart of consumption:

1. Poll for records with timeout.
2. Process records within `max.poll.interval.ms`.
3. Commit offsets after successful processing.
4. Handle exceptions without crashing the loop.

Processing must complete before the next poll deadline. Long-running processing triggers rebalance, losing partition assignments. For slow processing:

- Reduce `max.poll.records`.
- Increase `max.poll.interval.ms` (affects failure-detection latency).
- Offload processing to a thread pool; commit asynchronously.

### Offset Commit Strategies

| Strategy | Pros | Cons | Use Case |
|:---------|:-----|:-----|:---------|
| Auto-commit | Simple | Risks loss or duplication on failure | Simple processing |
| Sync commit after batch | Safe, no data loss | Adds latency | Safe processing |
| **Async commit + sync on shutdown** | **Best throughput with safety** | More complex | **Production (recommended)** |
| Per-message commit | Maximum safety | Minimum throughput | Critical low-volume data |

### Rebalance Handling

Rebalances occur when:

- A consumer joins or leaves the group.
- A consumer fails to heartbeat within session timeout.
- A consumer exceeds `max.poll.interval.ms`.
- Partition count changes.
- A subscription pattern matches new topics.

Implement `ConsumerRebalanceListener`:

- `onPartitionsRevoked` — commit offsets, flush state, release resources before partitions are taken.
- `onPartitionsAssigned` — initialize state for newly assigned partitions.

Use cooperative rebalancing (`partition.assignment.strategy=CooperativeStickyAssignor`) to minimize disruption — only changed partitions are revoked rather than all partitions.

---
[Back to Overview](./OVERVIEW.md)
