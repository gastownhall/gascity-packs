# Consumer Patterns

### Manual Acknowledgment

Acknowledge messages explicitly after successful processing:

1. Receive message.
2. Process message completely.
3. On success: `basic.ack`.
4. On failure: `basic.nack` or `basic.reject`.

Auto-acknowledgment removes messages from the queue on delivery, before processing completes. A crash loses the message. **Disable auto-ack for any workload where message loss matters.**

### Acknowledgment Semantics

- `basic.ack` — message processed successfully; remove from queue.
- `basic.nack` — processing failed; optionally requeue or dead-letter.
- `basic.reject` — single-message rejection; same semantics as nack.

Use `requeue=false` with dead-letter configuration to route failed messages for inspection rather than infinite retry loops.

### Prefetch (QoS)

Prefetch limits unacknowledged messages per consumer:

| `prefetch_count` | Distribution | Throughput | Use case |
|:----------------:|:------------:|:----------:|:---------|
| `1` | Fair | Low | Slow processing, fair work distribution |
| `10–50` | Some unfairness | Medium | Balanced performance and fairness |
| `100+` | Potentially unfair | High | Fast processing with batching benefits |
| `0` (unlimited) | Very unfair | Maximum | **Dangerous for memory consumption** |

Tune prefetch based on processing time, consumer memory, fairness needs, and network latency.

### Competing Consumers

Multiple consumers on one queue share work:

- Messages distributed round-robin by default.
- Prefetch settings affect distribution fairness.
- No ordering guarantees across consumers.
- Scale horizontally by adding consumers.

This pattern enables horizontal scaling of message processing without publisher changes.

### Consumer Tags

Assign meaningful tags to consumers for identification:

- Include service name, instance ID, processing purpose.
- Tags appear in management UI and monitoring.
- Enable correlation of consumer behavior with application instances.

### Consumer Cancellation

Handle broker-initiated consumer cancellation:

- Queue deleted while consumer active.
- Node failure in cluster.
- Administrative action.

Implement cancellation handlers that reconnect or alert. Consumers that ignore cancellation become silently disconnected.

### Poison Message Handling

Messages that consistently fail processing:

- Track retry count in message headers.
- Dead-letter after N failures.
- **Never requeue indefinitely without bounds.**
- Log failed messages with full context for debugging.

Implement retry limits in the consumer, not the broker. The broker handles routing; the application handles retry policy.

---
[Back to Overview](./OVERVIEW.md)
