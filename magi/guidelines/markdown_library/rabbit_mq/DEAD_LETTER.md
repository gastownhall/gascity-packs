# Dead Letter Handling

### Dead Letter Exchanges (DLX)

Messages route to dead letter exchanges when:

- Consumer rejects with `requeue=false`.
- Message TTL expires.
- Queue length limit exceeded.

Configure per-queue:

- `x-dead-letter-exchange` — target exchange.
- `x-dead-letter-routing-key` — override routing key (optional).

### DLX Topology

Standard pattern:

1. Main queue with DLX configured.
2. DLX routes to dead letter queue.
3. Dead letter queue holds failed messages for inspection.
4. Monitoring alerts on DLQ depth.

### Message Metadata

Dead-lettered messages include headers:

- `x-death` — array of death events with reason, queue, time.
- `x-first-death-reason` — why the message was first dead-lettered.
- `x-first-death-queue` — original queue name.

Use this metadata for debugging and retry logic.

### TTL Patterns

| Pattern | Argument / property | Behavior |
|:--------|:--------------------|:---------|
| Queue-level TTL | `x-message-ttl` on queue | All messages expire after the same duration |
| Per-message TTL | `expiration` in message properties | Each message has individual TTL; only expires at head of queue |
| Retry-via-TTL | `x-message-ttl` on retry queue + DLX | Backoff via increasing TTL |

### Retry Patterns

Implement retry with increasing delays:

1. Reject message to DLX.
2. DLX routes to retry queue with TTL.
3. TTL expiration routes back to main queue.
4. Track retry count in message headers.
5. Permanent dead-letter after max retries.

This creates a retry loop with backoff without consumer-side delay logic.

### DLQ Processing

| Strategy | Description |
|:---------|:------------|
| Manual inspection | Human review and replay via management UI or custom tooling |
| Automated retry | Programmatic retry with error correction; consumer on DLQ republishes after fix |
| Archival | Store for audit/compliance — move to long-term storage |

**Never ignore DLQ accumulation.** Growing DLQs indicate systemic processing failures.

---
[Back to Overview](./OVERVIEW.md)
