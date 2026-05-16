# Technology Comparison Matrix

### Core Characteristics

| Technology     | Data Model           | Consistency        | Scale                | Latency   | Cost              |
|----------------|----------------------|--------------------|----------------------|-----------|-------------------|
| SQL Server     | Relational           | Strong             | Vertical (+replicas) | Low       | Medium            |
| PostgreSQL     | Relational           | Strong             | Vertical (+replicas) | Low       | Low-Medium        |
| Cosmos DB      | Multi-model          | Configurable       | Horizontal           | Very Low  | High              |
| Redis          | Key-Value/Structures | Eventual (cluster) | Horizontal           | Ultra-Low | Medium-High       |
| Blob Storage   | Object               | Strong             | Unlimited            | Medium    | Very Low          |
| Storage Queues | Messages             | Eventual           | High                 | Low       | Very Low          |
| RabbitMQ       | Messages             | Strong (single)    | Medium               | Low       | Low (self-hosted) |

### Feature Comparison

| Feature             | SQL     | Cosmos           | Redis           | Blob       | Queues | RabbitMQ  |
|---------------------|---------|------------------|-----------------|------------|--------|-----------|
| ACID Transactions   | Yes     | Partition-scoped | No              | No         | No     | Per-queue |
| Complex Queries     | Yes     | Limited          | No              | No         | No     | No        |
| Secondary Indexes   | Yes     | Auto-indexed     | Limited         | No         | No     | No        |
| Global Distribution | Complex | Native           | Enterprise tier | Native     | No     | Manual    |
| TTL/Expiration      | Manual  | Native           | Native          | Lifecycle  | Yes    | Yes       |
| Pub/Sub             | No      | Change Feed      | Yes             | Event Grid | No     | Yes       |

### Operational Characteristics

| Technology     | Managed Options          | Self-Host | Expertise Needed | Monitoring |
|----------------|--------------------------|-----------|------------------|------------|
| SQL Server     | Azure SQL, RDS           | Yes       | Medium           | Mature     |
| PostgreSQL     | Azure, RDS, Cloud SQL    | Yes       | Medium           | Mature     |
| Cosmos DB      | Azure Only               | No        | High             | Good       |
| Redis          | Azure Cache, ElastiCache | Yes       | Medium           | Good       |
| Blob Storage   | Azure Only               | No        | Low              | Good       |
| Storage Queues | Azure Only               | No        | Low              | Basic      |
| RabbitMQ       | CloudAMQP                | Yes       | High             | Good       |

---
[Back to Overview](./OVERVIEW.md)
