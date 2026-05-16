# Pub/Sub and Messaging

### Redis Pub/Sub

Pub/Sub provides **at-most-once** message delivery:

- Fire-and-forget — messages delivered to connected subscribers only.
- No persistence — if no subscribers, message is lost.
- No acknowledgment — publisher doesn't know if message received.
- Pattern matching — subscribe to patterns (`user:*`).

| Use cases | Not suitable for |
|:----------|:-----------------|
| Real-time notifications where loss is acceptable | Guaranteed delivery requirements |
| Cache invalidation broadcasts | Message replay/history |
| Lightweight chat/presence systems | Work queues with exactly-once processing |
| Configuration change notifications | — |

### Pub/Sub in Clustered Redis

In Azure Cache for Redis clustering, Pub/Sub has specific behavior:

- `PUBLISH` is propagated to all nodes; all subscribers on all shards receive message.
- `SUBSCRIBE` — client subscribes on single node but receives messages from all nodes.
- Bandwidth — every message goes to every node; high message volume impacts all shards.

Heavy Pub/Sub traffic in clustered environment consumes cluster interconnect bandwidth. Monitor for impact on key operations.

### Pub/Sub vs Streams Decision Matrix

| Feature | Pub/Sub | Streams |
|:--------|:--------|:--------|
| Delivery guarantee | At-most-once (fire-and-forget) | At-least-once with acknowledgment |
| Persistence | No persistence; online subscribers only | Persistent; survives restart |
| Consumer groups | Not supported | Full consumer group support |
| Message history | No history | Full replay capability |
| Performance | Lower latency, higher throughput | Higher latency, lower throughput |
| Use when | Real-time notifications, cache invalidation | Work queues, event sourcing, audit logs |

### Redis Streams for Reliable Messaging

Streams provide persistent, replayable message logs with consumer group support:

- Persistent — messages survive restart.
- Consumer groups — multiple consumers process different messages.
- Acknowledgment — `XACK` confirms processing.
- Dead letter handling — `XCLAIM` for failed message reprocessing.
- Replay — read from any point in history.

```text
# Producer
XADD stream * field1 value1

# Consumer
XREADGROUP GROUP mygroup myconsumer STREAMS stream >
# Process message
XACK stream mygroup message-id
```

**Stream maintenance:** `XTRIM stream MAXLEN ~ 10000` caps stream size (approximate for performance). Old messages automatically removed.

### Pub/Sub for Cache Invalidation

Broadcast pattern for multi-instance cache invalidation:

1. Instance A updates data in database.
2. Instance A publishes invalidation: `PUBLISH cache:invalidate {"key":"product:123"}`.
3. All instances (including A) receive message.
4. Each instance evicts `product:123` from local cache.
5. Next read fetches fresh data from Redis or database.

Implementation notes: dedicated subscriber connection per instance; reconnect logic for subscriber failures; local cache eviction (Redis already updated); handle missed invalidations gracefully (local TTL provides eventual consistency).

---
[Back to Overview](./OVERVIEW.md)
