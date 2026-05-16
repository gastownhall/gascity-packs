# Publisher Patterns

### Publisher Confirms

Enable publisher confirms for delivery acknowledgment:

1. Publisher sends message.
2. Broker routes message to queue(s).
3. Broker sends `basic.ack` (success) or `basic.nack` (failure).
4. Publisher handles confirmation.

Without confirms, publishers have no delivery feedback. **Fire-and-forget is appropriate only when message loss is acceptable — which is rarely.**

### Confirm Strategies

| Strategy | Throughput | Complexity | Use case |
|:---------|:----------:|:----------:|:---------|
| Synchronous | Low | Simple | Low volume or strict ordering |
| Batch | Medium | Medium | Moderate volume with batch processing |
| Asynchronous | High | Complex | High volume production workloads |

- **Synchronous confirms** — wait for each message confirmation before sending next. Simple but slow.
- **Batch confirms** — send multiple messages, then wait for all confirms. Better throughput but complex error handling when batch partially fails.
- **Asynchronous confirms** — track outstanding messages, handle confirms via callback. Maximum throughput with full reliability. Requires careful correlation of confirms to messages.

### Mandatory Publishing

The `mandatory` flag returns unroutable messages to the publisher:

- Message reaches no queue due to routing/binding mismatch.
- Broker returns message via `basic.return`.
- Publisher handles return (log, retry, alert).

Without `mandatory`, unroutable messages vanish silently. Enable for messages that must reach at least one queue.

### Immediate Publishing (Removed)

The `immediate` flag was **removed in RabbitMQ 3.0**. Do not attempt to use it. Design systems that handle consumer unavailability through queuing, not publisher-side detection.

### Transaction vs Confirms

AMQP transactions (`tx.select`, `tx.commit`, `tx.rollback`) are slow. Publisher confirms provide equivalent guarantees with better performance. **Use confirms, not transactions.**

### Retry and Circuit Breaker

Publishers must handle transient failures:

| Failure | Action |
|:--------|:-------|
| Connection loss | Reconnect with exponential backoff |
| Channel error | Recreate channel |
| `basic.nack` | Retry with backoff, eventual dead-letter |
| Sustained failure | Circuit breaker — stop publishing temporarily; resume after cooldown |

**Never retry indefinitely without backoff. Never ignore failures silently.**

---
[Back to Overview](./OVERVIEW.md)
