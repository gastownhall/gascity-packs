# Producer Patterns

### Producer Configuration

Critical producer settings for production:

**Durability:**

| Property | Value | Purpose |
|:---------|:------|:--------|
| `acks` | `all` | Wait for all in-sync replicas to acknowledge |
| `enable.idempotence` | `true` | Prevent duplicates from retries |
| `max.in.flight.requests.per.connection` | `5` | Safe for ordering with idempotence enabled |

**Reliability:**

| Property | Value |
|:---------|:------|
| `retries` | `2147483647` (rely on `delivery.timeout.ms` for bounds) |
| `delivery.timeout.ms` | `120000` |
| `request.timeout.ms` | `30000` |

**Performance:**

| Property | Value | Notes |
|:---------|:------|:------|
| `batch.size` | `65536` | Larger batches improve throughput |
| `linger.ms` | `5` | Balance latency vs throughput |
| `compression.type` | `lz4` | `lz4` for speed, `zstd` for ratio |

### Synchronous vs Asynchronous Sends

**Asynchronous (default, recommended)**:

- Producer batches messages and sends in the background.
- Callbacks handle success and failure.
- Higher throughput; the application continues without blocking.
- Requires proper callback error handling.

**Synchronous**:

- Block until broker acknowledges.
- Simpler error handling but dramatically lower throughput.
- Use only when processing cannot continue without confirmation.

### Error Handling

Producers must handle:

- **Retriable errors** — network timeouts, leader elections, broker unavailability. SDK retries automatically.
- **Non-retriable errors** — invalid message size, authorization failures, unknown topic. Fail immediately.
- **Callback exceptions** — errors in asynchronous send callbacks. Log and handle without crashing the producer.

Implement dead letter handling for messages that fail after all retries (see §12). Log failed messages with full context for manual recovery.

### Idempotent Producer

```properties
enable.idempotence=true
acks=all
```

Provides exactly-once delivery from a single producer to a single partition:

- Producer assigns sequence numbers to messages.
- Broker deduplicates based on producer ID and sequence.
- Retries do not cause duplicates.

**Limitations:**

- Single producer session — a new producer instance gets a new producer ID.
- Does not span multiple partitions atomically.
- Does not coordinate with consumer processing.

### Transactional Producer

For atomic writes across partitions:

```properties
enable.idempotence=true
transactional.id={unique-stable-id}
```

Workflow:

1. Initialize transactions on startup.
2. Begin transaction before sending.
3. Send to multiple partitions/topics.
4. Commit or abort atomically.

Consumers with `isolation.level=read_committed` see only committed messages.

---
[Back to Overview](./OVERVIEW.md)
