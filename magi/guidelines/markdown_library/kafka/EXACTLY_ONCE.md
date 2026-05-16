# Exactly-Once Semantics

### Idempotent Producer

See §4. Provides exactly-once delivery from a single producer to a single partition. **Limitations**: single producer session, does not span multiple partitions atomically, does not coordinate with consumer processing.

### Transactional Producer

For atomic writes across partitions — see §4 for configuration. Consumers with `isolation.level=read_committed` see only committed messages. Uncommitted messages are filtered.

### End-to-End Exactly-Once Pipeline

```properties
# Producer
enable.idempotence=true
transactional.id={stable-id}
acks=all

# Consumer
isolation.level=read_committed
enable.auto.commit=false
```

Implementation:

1. Begin transaction.
2. Consume messages.
3. Process messages.
4. Produce results.
5. Commit consumer offsets within transaction.
6. Commit transaction atomically.

### Exactly-Once with External Systems

Kafka alone cannot guarantee exactly-once for external system writes. Two approaches:

**Transactional outbox:**

1. Store processing results in database.
2. Store offsets in same transaction.
3. Commit database transaction atomically.

**Idempotent processing:**

1. Make processing idempotent using unique IDs.
2. Safe to replay on failure.

### Kafka Streams

Kafka Streams provides exactly-once processing semantics natively:

- Consume, process, produce in a single transaction.
- Offset commits included in transaction.
- Failure rolls back processing and output.

---
[Back to Overview](./OVERVIEW.md)
