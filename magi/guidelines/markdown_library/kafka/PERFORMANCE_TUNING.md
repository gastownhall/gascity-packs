# Performance Tuning

### Tuning Profiles

**High-throughput:**

```properties
# Producer
batch.size=1048576
linger.ms=100
compression.type=lz4
buffer.memory=134217728

# Consumer
fetch.min.bytes=1048576
max.poll.records=1000
```

**Low-latency:**

```properties
# Producer
batch.size=16384
linger.ms=0
compression.type=none

# Consumer
fetch.min.bytes=1
fetch.max.wait.ms=100
```

**Balanced (default):**

```properties
# Producer
batch.size=65536
linger.ms=5
compression.type=lz4

# Consumer
fetch.min.bytes=1024
max.poll.records=500
```

### Producer Tuning

For throughput:

- Increase `batch.size` (up to 1 MB).
- Increase `linger.ms` (5–100 ms based on latency tolerance).
- Enable compression (`lz4` or `zstd`).
- Increase `buffer.memory` if sends block waiting for buffer space.

For latency:

- Decrease `linger.ms` (0–5 ms).
- Decrease `batch.size` (smaller batches, more frequent sends).
- Ensure adequate network bandwidth.
- Co-locate producers with brokers when possible.

### Consumer Tuning

For throughput:

- Increase `fetch.min.bytes` (larger fetches, fewer requests).
- Increase `max.poll.records`.
- Process records in parallel within poll batch.
- Use multiple consumers in group to parallelize across partitions.

For latency:

- Decrease `fetch.min.bytes` and `fetch.max.wait.ms`.
- Process records immediately without batching.
- Ensure consumer processing is not the bottleneck.

### Broker Tuning

| Property | Default | Notes |
|:---------|:--------|:------|
| `num.network.threads` | 3 | Increase if network bottleneck; up to number of CPU cores |
| `num.io.threads` | 8 | Scale with disk count for disk-heavy workloads |
| `socket.send.buffer.bytes` / `socket.receive.buffer.bytes` | — | Increase for high-throughput / high-latency networks |
| `log.flush.interval.messages` / `log.flush.interval.ms` | — | Defaults rely on OS page cache and replication; typically leave unchanged |

### OS and JVM Tuning

OS:

- File descriptor limits ≥ 100,000.
- `vm.swappiness=1` to minimize swapping.
- Increase `net.core.rmem_max` and `net.core.wmem_max`.
- Use XFS filesystem for log directories.

JVM:

- Heap 6–8 GB typical; larger heaps increase GC pause risk.
- G1GC for most deployments.
- Enable GC logging.
- `-XX:MaxGCPauseMillis=20` for target pause time.

---
[Back to Overview](./OVERVIEW.md)
