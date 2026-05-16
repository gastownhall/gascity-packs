# Core Principles

These guidelines define strict, scalable, and operationally sound patterns for Apache Kafka deployments, optimizing for:

- **Immutable Log Semantics**: Kafka is an append-only commit log; messages are immutable once written. Design systems around this constraint rather than fighting it.
- **Partition-Aware Architecture**: Partitions are the unit of parallelism, ordering, and scalability. Every design decision flows from partition strategy.
- **Consumer Autonomy**: Consumers own their offsets and replay capability. The broker does not track consumption state beyond commit markers.
- **Durability Through Replication**: Data survives broker failures only through proper replication configuration. Single-replica topics are development conveniences, not production artifacts.
- **Backpressure by Design**: Kafka does not push to consumers; consumers pull at their own pace. Design systems that leverage this property for resilience.

### Primary Rule: Kafka Is Not a Message Queue

Kafka is a distributed commit log with pub/sub semantics layered on top. Message queues delete messages after consumption; Kafka retains messages based on time or size policies regardless of consumption. Queues guarantee single delivery to one consumer; Kafka allows unlimited consumers to read the same messages independently. Designing Kafka like RabbitMQ or SQS produces systems that miss Kafka's strengths and stumble over its operational model.

### Secondary Rule: Partition Count Is a One-Way Door

Partitions can be added but never removed without recreating the topic. Adding partitions breaks key-based ordering guarantees for existing keys. The initial partition count decision constrains the system for its lifetime. Invest heavily in getting it right.

### Kafka's Role in System Architecture

Kafka excels at:

- Event sourcing and event-driven architectures where history matters
- High-throughput ingestion pipelines tolerating latency for throughput
- Decoupling producers from consumers with independent scaling
- Replay scenarios where consumers need historical data reprocessing
- Stream processing with stateful transformations

Kafka is not optimal for:

- Request-response patterns requiring immediate acknowledgment
- Low-latency messaging below 10 ms end-to-end requirements
- Small message volumes where operational overhead exceeds value
- Transactional workflows requiring message deletion after processing

---
[Back to Overview](./OVERVIEW.md)
