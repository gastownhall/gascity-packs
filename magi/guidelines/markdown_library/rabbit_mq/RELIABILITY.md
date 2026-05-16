# Reliability and Durability

### Message Persistence

For messages to survive broker restart:

1. Queue must be durable.
2. Message `delivery_mode` must be `2` (persistent).
3. Disk write must complete before acknowledgment.

Persistent messages have higher latency than transient. Accept the tradeoff for reliability or use quorum queues where persistence is the default.

### Publisher-Side Reliability

Complete reliability chain for publishers:

1. Enable publisher confirms.
2. Handle confirms/nacks appropriately.
3. Persist unpublished messages locally until confirmed.
4. Implement retry with exponential backoff.
5. Use mandatory flag if routing to at least one queue is required.

### Consumer-Side Reliability

Complete reliability chain for consumers:

1. Disable auto-acknowledgment.
2. Process message completely before acknowledging.
3. Acknowledge with `basic.ack` on success.
4. Reject with `basic.nack requeue=false` on permanent failure.
5. Configure dead-letter exchange for rejected messages.

### Delivery Guarantees

| Guarantee | Mechanism | Notes |
|:----------|:----------|:------|
| At-least-once | Acknowledge after processing | Production default; requires idempotent consumers |
| At-most-once | Auto-ack on receive | Acceptable only when message loss is tolerable |
| Exactly-once | At-least-once + dedup | Not natively supported; achieve via idempotent processing with deduplication |

### Transactions

AMQP transactions provide atomic publish batches:

- `tx.select` — enter transaction mode.
- Publish messages.
- `tx.commit` — commit all messages atomically.
- `tx.rollback` — discard all messages.

Transactions are slow. Publisher confirms with application-level compensation provide better performance for most use cases.

---
[Back to Overview](./OVERVIEW.md)
