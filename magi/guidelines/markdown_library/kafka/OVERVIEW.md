# Apache Kafka Library

These guidelines define strict, scalable, and operationally sound patterns for Apache Kafka deployments, optimizing for immutable log semantics, partition-aware architecture, consumer autonomy, durability through replication, and backpressure by design.

## Critical Mandates (Read First)
- **Kafka Is Not a Message Queue** — distributed commit log with pub/sub semantics; design accordingly.
- **Partition Count Is a One-Way Door** — can be added, never removed without recreating the topic.
- **Replication Factor 3 Minimum** for production topics with `min.insync.replicas=2`.
- **Idempotent Producers** — `acks=all` + `enable.idempotence=true` always.
- **Manual Offset Commits** for exactly-once consumers; never auto-commit.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [Topic Design and Naming](./TOPIC_DESIGN_NAMING.md)
3. [Partitioning Strategy](./PARTITIONING_STRATEGY.md)
4. [Producer Patterns](./PRODUCER_PATTERNS.md)
5. [Consumer Patterns](./CONSUMER_PATTERNS.md)
6. [Message Design and Serialization](./MESSAGE_DESIGN.md)
7. [Schema Management](./SCHEMA_MANAGEMENT.md)
8. [Retention and Storage](./RETENTION_STORAGE.md)
9. [Replication and Durability](./REPLICATION_DURABILITY.md)
10. [Exactly-Once Semantics](./EXACTLY_ONCE.md)
11. [Consumer Group Management](./CONSUMER_GROUPS.md)
12. [Error Handling — Dead Letter and Retry](./ERROR_HANDLING.md)
13. [Log Compaction](./LOG_COMPACTION.md)
14. [Stream Processing — Kafka Streams vs ksqlDB](./STREAM_PROCESSING.md)
15. [Kafka Connect](./KAFKA_CONNECT.md)
16. [Security Configuration](./SECURITY.md)
17. [Monitoring and Operations](./MONITORING.md)
18. [Performance Tuning](./PERFORMANCE_TUNING.md)
19. [Cluster Sizing and Capacity](./CLUSTER_SIZING.md)
20. [Shakedown — End-to-End Cluster Validation](./SHAKEDOWN.md)
21. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
22. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
23. [Required Practices](./REQUIRED_PRACTICES.md)
24. [Style Summary](./STYLE_SUMMARY.md)
