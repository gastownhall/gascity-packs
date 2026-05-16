# Connection and Channel Management

### Connection Lifecycle

Connections are TCP connections to the broker:

- Expensive to create (TLS handshake, authentication, protocol negotiation).
- Designed for long-lived use.
- One connection per application instance is typically sufficient.
- Heartbeats detect stale connections; configure based on network characteristics.

### Channel Multiplexing

Channels are lightweight virtual connections within a connection:

- Cheap to create and destroy.
- **Not thread-safe** — one channel per thread or use locking.
- Each channel has independent flow control.
- Publishers and consumers can share connections but typically use separate channels.

### Channel Allocation Patterns

| Strategy | Thread safety | Complexity | Recommendation |
|:---------|:--------------|:-----------|:---------------|
| Thread-dedicated (one per thread) | Safe by design | Simple | **Preferred for multi-threaded apps** |
| Channel pool | Requires synchronization | Complex | High-frequency short operations |
| Dedicated channels (publish vs consume) | Per-thread | Moderate | Isolate flow control and errors |

**Anti-pattern:** creating a new connection per operation.

### Connection Recovery

Implement automatic recovery for resilience:

1. Detect connection loss via exception or heartbeat timeout.
2. Reconnect with exponential backoff.
3. Recreate channels after connection recovery.
4. Redeclare topology (queues, exchanges, bindings) if not using exclusive/auto-delete.
5. Resume consuming with same consumer tags.

Most client libraries provide built-in recovery. **Enable and configure it; do not roll your own** unless the library's behavior is insufficient.

### Heartbeats

Heartbeats detect dead connections:

- Broker and client exchange heartbeat frames.
- Connection closed if heartbeats missed.
- Default 60 seconds.

| Network type | Heartbeat | Rationale |
|:-------------|:---------:|:----------|
| Reliable (datacenter) | 60–120s | Less overhead, slower detection acceptable |
| Unreliable | 10–30s | Faster dead-connection detection |
| Cloud environments | 30s | Balance between detection and overhead |

Connection closes if `(heartbeat_interval × 2)` elapses without traffic.

### Blocked Connection Handling

When the broker experiences resource pressure, it blocks publishing connections:

- Memory alarm: broker memory exceeds threshold.
- Disk alarm: disk space below threshold.
- Publishers block until pressure relieved.

Implement blocked-connection callbacks to alert operators rather than waiting indefinitely.

---
[Back to Overview](./OVERVIEW.md)
