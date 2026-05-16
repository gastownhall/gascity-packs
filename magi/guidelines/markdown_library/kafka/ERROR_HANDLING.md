# Error Handling — Dead Letter and Retry

### Dead Letter Queue

Handle poison messages without blocking processing.

**Producer DLQ:**

1. Catch producer exceptions.
2. Send failed messages to DLQ topic.
3. Include error context in headers.
4. Continue processing.

**Consumer DLQ:**

1. Catch processing exceptions.
2. Send to DLQ after max retries.
3. Commit original offset.
4. Monitor DLQ for manual intervention.

**Connect DLQ:**

```properties
errors.tolerance=all
errors.deadletterqueue.topic.name={topic}.dlq
errors.deadletterqueue.context.headers.enable=true
```

**DLQ monitoring:**

- Alert on `dlq-message-rate > 0` — investigate poison messages.
- Track `dlq-lag` — messages awaiting manual processing.

### Retry Topic Pattern

Automatic retry with backoff:

```text
main-topic
  ↓ (failure)
retry-topic-1   (delay: 1 min)
  ↓ (failure)
retry-topic-2   (delay: 5 min)
  ↓ (failure)
retry-topic-3   (delay: 30 min)
  ↓ (failure)
dlq-topic       (final)
```

Each retry topic has its own consumer group with delayed processing. Failed messages flow through retry tiers before landing in DLQ for manual intervention.

---
[Back to Overview](./OVERVIEW.md)
