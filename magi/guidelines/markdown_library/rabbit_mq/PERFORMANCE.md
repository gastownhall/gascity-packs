# Performance Tuning

### Memory Management

| Parameter | Default | Description |
|:----------|:-------:|:------------|
| `vm_memory_high_watermark` | `0.4` | Fraction of RAM before flow control |
| `vm_memory_high_watermark_paging_ratio` | `0.5` | When to start paging to disk |

Flow control protects the broker but degrades publisher throughput. Size memory appropriately for expected queue depth.

### Disk Performance

Persistent messages require disk I/O:

- Use SSDs for production message storage.
- Separate message storage from OS disk.
- Monitor disk latency; high latency indicates storage bottleneck.
- `disk_free_limit` (default 50MB) — minimum free space before blocking.

### Connection Limits

Prevent resource exhaustion:

| Parameter | Description |
|:----------|:------------|
| `max_connections` | Per-node connection limit; expected + 20% headroom |
| `channel_max` | Maximum channels per connection (default 2047) |

Plan for expected connection count plus headroom. Monitor file descriptor usage.

### Queue Performance

Optimize queue throughput:

- Use quorum queues for replication; classic for single-node.
- Enable lazy queues for large, slow-draining queues.
- Set appropriate message TTL to prevent unbounded growth.
- Match prefetch to consumer processing capacity.

### Network Optimization

For high-throughput deployments:

- Co-locate publishers and consumers with broker.
- Use dedicated network for cluster communication.
- Configure TCP keepalive and buffer sizes.
- Consider larger frame sizes for large messages.

### Benchmark Methodology

Measure before tuning:

- Use **PerfTest** (official RabbitMQ tool) for throughput benchmarking.
- Test realistic message sizes and patterns.
- Measure latency percentiles (p50, p95, p99).
- Profile before optimizing.

---
[Back to Overview](./OVERVIEW.md)
