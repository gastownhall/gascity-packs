# Data Storage and Messaging Technology Selection Library

This guide defines strict, practical criteria for selecting the right data storage or messaging technology for each use case. The goal is eliminating ambiguity in technology decisions, preventing architectural mistakes that require expensive migrations, and ensuring each component uses the technology that matches its access patterns.

- **Right Tool for the Job**: No single technology solves all problems; each has specific strengths and trade-offs
- **Access Pattern Alignment**: Storage technology must match how data is read, written, and queried
- **Consistency Requirements**: Understand CAP theorem implications for each choice
- **Operational Cost Awareness**: Factor in not just price, but operational complexity, monitoring, and failure modes
- **Future-Proofing Without Over-Engineering**: Choose for current needs with awareness of scaling paths

## Critical Mandates (Read First)

- **Start with Requirements, Not Technology** — Never begin with "we should use Cosmos DB" or "let's add Redis"; begin with access patterns, consistency, structure, scale, latency, durability, and query complexity.
- **Complexity Has Ongoing Costs** — Every technology added increases operational burden, cognitive load, failure surface area, and integration complexity; a simpler architecture with fewer technologies is preferable.
- **Migrations Are Expensive** — Choosing the wrong storage technology creates technical debt; migrating is one of the most expensive and risky operations in software development.
- **Shakedown After Every Triggering Change** — Cutover of producer-broker-consumer or client-store changes without a recorded shakedown result is prohibited.

## Table of Contents

### Foundation

1. [Core Principles](./CORE_PRINCIPLES.md)

### Part I: Technology Overview

2. [Relational Databases (SQL Server, PostgreSQL, MySQL)](./RELATIONAL_DATABASES.md)
3. [Azure Cosmos DB](./COSMOS_DB.md)
4. [Redis](./REDIS.md)
5. [Azure Blob Storage](./BLOB_STORAGE.md)
6. [Azure Storage Queues](./STORAGE_QUEUES.md)
7. [RabbitMQ](./RABBIT_MQ.md)
8. [In-Process / In-Memory Solutions](./IN_PROCESS.md)

### Part II: Decision Framework

9. [Access Pattern Analysis](./ACCESS_PATTERNS.md)
10. [Decision Trees](./DECISION_TREES.md)
11. [Anti-Patterns to Avoid](./ANTI_PATTERNS.md)
12. [Multi-Technology Architectures](./MULTI_TECHNOLOGY.md)
13. [Consistency Considerations](./CONSISTENCY.md)

### Part III: Implementation Patterns

14. [Caching Patterns](./CACHING_PATTERNS.md)
15. [Event-Driven Patterns](./EVENT_DRIVEN.md)
16. [Data Access Patterns](./DATA_ACCESS.md)
17. [Resilience Patterns](./RESILIENCE.md)

### Part IV: Technology Deep Dives

18. [Cosmos DB Advanced Patterns](./COSMOS_ADVANCED.md)
19. [Redis Advanced Patterns](./REDIS_ADVANCED.md)
20. [Blob Storage Advanced Patterns](./BLOB_ADVANCED.md)
21. [Backup Strategy Decision Tree](./BACKUP_STRATEGY.md)
22. [Anti-Pattern Code Examples](./ANTI_PATTERN_EXAMPLES.md)
23. [Monitoring and Observability — Required Telemetry](./MONITORING.md)

### Part V: Comparative Analysis and Future Considerations

24. [Technology Comparison Matrix](./COMPARISON_MATRIX.md)
25. [Kafka and Event Hubs](./KAFKA_EVENT_HUBS.md)
26. [Snowflake](./SNOWFLAKE.md)
27. [Making Future-Proof Decisions](./MIGRATION.md)
28. [Technology Selection Checklist](./SELECTION_CHECKLIST.md)
29. [Quick Reference Matrix](./QUICK_REFERENCE.md)

### Part VI: Shakedown

30. [Shakedown — Cross-Cutting Integration Validation](./SHAKEDOWN.md)

### Part VII: Defense in Depth

31. [Defense in Depth](./DEFENSE_IN_DEPTH.md)

### Summary

32. [Style Summary](./STYLE_SUMMARY.md)
