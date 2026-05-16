# Kafka and Event Hubs

### When to Consider Kafka/Event Hubs

Kafka and Azure Event Hubs (Kafka-compatible) are designed for different patterns than traditional message queues:

**Log-Based Event Streaming**:
- Events stored as immutable log
- Consumers track their own position (offset)
- Same event consumed by multiple consumers
- Event replay from any point in time
- Retention-based (days/weeks) not delivery-based

### Ideal Use Cases

- High-throughput event ingestion (>100K events/second)
- Event sourcing at scale
- Real-time analytics pipelines
- Multiple independent consumers of same events
- Event replay requirements
- Audit logs requiring immutability

### Comparison with Traditional Queues

| Aspect     | Message Queues                        | Kafka/Event Hubs                         |
|------------|---------------------------------------|------------------------------------------|
| Delivery   | Message deleted after consumption     | Message retained, consumer tracks offset |
| Consumers  | Typically single consumer per message | Multiple consumers read same messages    |
| Replay     | Not supported                         | Replay from any offset                   |
| Ordering   | Queue-level or no guarantee           | Partition-level ordering                 |
| Throughput | Moderate (thousands/sec)              | High (millions/sec)                      |
| Latency    | Sub-second                            | Sub-second to seconds                    |
| Use Case   | Task queues, decoupling               | Event streaming, analytics               |

### When NOT to Use Kafka

- Simple point-to-point messaging (overkill)
- Low volume (<1K events/second) with no replay needs
- Request-response patterns
- When team lacks streaming expertise
- When operational complexity budget is limited

### Azure Event Hubs Tiers

| Tier      | Throughput       | Partitions | Retention | Use Case         |
|-----------|------------------|------------|-----------|------------------|
| Basic     | 1 MB/s ingress   | 32 max     | 1 day     | Development      |
| Standard  | 20 MB/s ingress  | 32 max     | 7 days    | Production       |
| Premium   | 100 MB/s ingress | 100 max    | 90 days   | High-scale       |
| Dedicated | 100+ MB/s        | 1000+      | 90+ days  | Mission-critical |

---
[Back to Overview](./OVERVIEW.md)
