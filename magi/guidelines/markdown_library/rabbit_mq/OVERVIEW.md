# RabbitMQ Library

These guidelines define strict, reliable, and scalable patterns for RabbitMQ message broker implementations.

## Critical Mandates (Read First)
- **Acknowledge What You Complete** — manual ack after successful processing is non-negotiable.
- **Exchanges Route, Queues Buffer** — honor the separation.
- **Quorum Queues for Production HA** — classic mirrored queues deprecated.
- **3-Node Cluster Minimum** — one fails with no message loss and no availability impact.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [Architecture and Topology Design](./ARCHITECTURE.md)
3. [Exchange Types and Routing](./EXCHANGES.md)
4. [Queue Configuration](./QUEUES.md)
5. [Message Design and Serialization](./MESSAGE_DESIGN.md)
6. [Publisher Patterns](./PUBLISHER_PATTERNS.md)
7. [Consumer Patterns](./CONSUMER_PATTERNS.md)
8. [Connection and Channel Management](./CONNECTIONS_CHANNELS.md)
9. [Reliability and Durability](./RELIABILITY.md)
10. [Clustering and High Availability](./CLUSTERING.md)
11. [Security Configuration](./SECURITY.md)
12. [Monitoring and Observability](./MONITORING.md)
13. [Performance Tuning](./PERFORMANCE.md)
14. [Dead Letter Handling](./DEAD_LETTER.md)
15. [Integration Patterns](./INTEGRATION.md)
16. [Shakedown — Integration Validation](./SHAKEDOWN.md)
17. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
18. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
19. [Required Practices](./REQUIRED_PRACTICES.md)
20. [Style Summary](./STYLE_SUMMARY.md)
