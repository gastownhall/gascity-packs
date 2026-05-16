# Queue Configuration

### Durability Settings

**Durable queues** survive broker restarts. Non-durable queues vanish when the broker stops. Production queues must be durable unless explicitly designed for ephemeral workloads.

**Persistent messages** (delivery mode 2) are written to disk. Non-persistent messages exist only in memory. Durable queues with non-persistent messages lose messages on restart. **Match message persistence to queue durability.**

| Configuration | Queue durable | Delivery mode | Use case |
|:--------------|:-------------:|:-------------:|:---------|
| `production-persistent` | true | 2 | Production workloads requiring data durability |
| `ephemeral-fast` | false | 1 | Transient data; loss is acceptable |
| `durable-transient` | true | 1 | Queue topology persistence without message overhead — messages lost on restart |

### Queue Arguments

Configure queue behavior through arguments at declaration:

| Argument | Type | Description |
|:---------|:-----|:------------|
| `x-message-ttl` | milliseconds | Message expiration; routed to DLX if configured |
| `x-expires` | milliseconds | Queue auto-deletion after idle period |
| `x-max-length` | integer | Maximum message count before drop or DLX |
| `x-max-length-bytes` | bytes | Maximum queue size in bytes |
| `x-overflow` | enum | `drop-head`, `reject-publish`, `reject-publish-dlx` |
| `x-dead-letter-exchange` | string | Target exchange for rejected/expired messages |
| `x-dead-letter-routing-key` | string | Override routing key for dead-lettered messages |
| `x-queue-type` | enum | `classic` or `quorum` |
| `x-max-priority` | integer | Enable priority queue with max priority level (1–255) |
| `x-queue-mode` | enum | `default` or `lazy` |

### Quorum Queues

Quorum queues use Raft consensus for replication:

- Replicated across multiple nodes by default.
- Stronger durability guarantees than classic mirrored queues.
- Higher latency for publishes (consensus required).
- Automatic leader election on failure.
- **Recommended for all new production workloads requiring HA.**

Declare quorum queues with `x-queue-type: quorum`. They replace classic mirrored queues as the HA solution.

### Classic Queues

Classic queues are single-node by default:

- Lower latency than quorum queues.
- No built-in replication (mirroring deprecated).
- Suitable for transient workloads or when paired with external HA.

Use classic queues only when quorum queue overhead is measured and unacceptable, or for explicitly ephemeral use cases.

### Lazy Queues

Lazy queues move messages to disk aggressively:

- Reduce memory pressure for large queues.
- Higher latency for message access.
- Useful when queue depth routinely exceeds memory capacity.

Enable with `x-queue-mode: lazy`. Consider for queues expected to accumulate during consumer downtime.

### Priority Queues

Messages are processed in priority order rather than FIFO:

- Configure with `x-max-priority: <N>` (1–255).
- Publishers set `priority: 0..N` per message.
- Higher CPU and memory overhead than standard queues.

**Constraint:** All publishers must set priority or messages default to 0. Use only when critical messages must jump the queue.

### Queue Length Limits

Unbounded queues are production incidents waiting to happen. Configure limits:

- `x-max-length` — cap message count.
- `x-max-length-bytes` — cap total size.
- `x-overflow: reject-publish-dlx` — dead-letter excess messages rather than dropping silently.

Publishers must handle `basic.nack` when queues reject due to overflow. **This is backpressure — embrace it.**

### Exclusive and Auto-Delete Queues

**Exclusive queues** are bound to the declaring connection and deleted when it closes. Use for temporary reply queues in RPC patterns.

**Auto-delete queues** are removed when the last consumer disconnects. Use for temporary consumer-specific queues.

Neither survives connection loss. **Never use for durable workloads.**

---
[Back to Overview](./OVERVIEW.md)
