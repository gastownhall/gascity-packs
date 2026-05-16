# Azure Cosmos DB

### What It Is

Cosmos DB is Microsoft's globally distributed, multi-model database service. It provides turnkey global distribution, horizontal scaling, and multiple consistency levels. It supports document, key-value, graph, and column-family data models through different APIs.

### Core Strengths

- **Global Distribution**: Data automatically replicated across Azure regions with configurable consistency
- **Horizontal Scaling**: Scales throughput and storage independently across partitions
- **Multiple Consistency Levels**: Five levels from strong to eventual; choose per-operation
- **Low Latency**: Single-digit millisecond reads and writes at the 99th percentile (with proper partitioning)
- **Multi-Model**: SQL API (documents), MongoDB API, Cassandra API, Gremlin (graph), Table API
- **Serverless Option**: Pay-per-request for unpredictable or bursty workloads
- **Automatic Indexing**: All properties indexed by default; no index management required

### Core Weaknesses

- **Cost**: Significantly more expensive than relational databases for equivalent workloads
- **Query Limitations**: No JOINs across partitions; cross-partition queries are expensive
- **Partition Key Lock-In**: Choosing the wrong partition key is catastrophic and requires data migration
- **RU Model Complexity**: Request Units are non-intuitive; estimating costs requires understanding query patterns
- **Transaction Scope**: Transactions limited to single partition; cross-partition transactions require Transactional Batch
- **Eventual Consistency Complexity**: Understanding and testing eventual consistency is difficult

### Ideal Use Cases

- Globally distributed applications requiring low-latency access in multiple regions
- High-throughput scenarios exceeding single-node relational database capacity
- Document-oriented data with varying schemas
- IoT telemetry and event ingestion at massive scale
- Shopping carts, user profiles, catalog data with clear partition keys
- Applications requiring multiple consistency levels per operation

### Avoid When

- Strong transactional consistency across multiple entities is required
- Complex ad-hoc queries with JOINs are common
- Cost is a primary concern and workload fits single-node relational
- Data relationships are complex and require referential integrity
- Partition key selection is unclear or data access patterns are unknown
- Team lacks experience with distributed database concepts

### Partition Key Selection

The partition key decision is the most critical Cosmos DB design choice. Get it wrong, and you face:
- Hot partitions (all traffic hits one partition)
- Cross-partition queries (expensive, slow)
- Data migration to fix it (extremely painful)

Partition key requirements:
- High cardinality (many distinct values)
- Even distribution of data and request volume
- Included in most queries as an equality filter
- Stable (doesn't change for a given document)

Good partition keys:
- `tenantId` for multi-tenant applications
- `userId` for user-centric applications
- `deviceId` for IoT scenarios
- `orderId` for order management (if queries are order-centric)

Bad partition keys:
- `status` (low cardinality, hot partitions)
- `createdDate` (hot partition on current date)
- `country` (uneven distribution)
- Anything with fewer than 1000 distinct values

### Consistency Levels

| Level                 | Guarantee                           | Latency | Use Case                          |
|-----------------------|-------------------------------------|---------|-----------------------------------|
| **Strong**            | Linearizable reads                  | Highest | Financial transactions, inventory |
| **Bounded Staleness** | Reads lag by K versions or T time   | High    | Leaderboards with tolerance       |
| **Session**           | Monotonic reads within session      | Medium  | User sessions, shopping carts     |
| **Consistent Prefix** | Reads never see out-of-order writes | Low     | Social feeds, timelines           |
| **Eventual**          | No ordering guarantees              | Lowest  | Telemetry, non-critical counters  |

Default to Session consistency for most applications; it provides read-your-writes within a session at reasonable cost.

### Request Unit (RU) Model

Every operation consumes Request Units based on:
- Document size
- Query complexity
- Index utilization
- Consistency level

Rough RU guidelines:
- Point read (1KB document by ID and partition key): ~1 RU
- Point write (1KB document): ~5-10 RU
- Query returning 10 documents: ~10-100 RU (depends on complexity)
- Cross-partition query: 2.5x multiplier per partition touched

Monitor RU consumption religiously. Unexpected RU spikes indicate query problems or hot partitions.

### Cost Optimization

- Use serverless for development and low/unpredictable traffic
- Use provisioned throughput with autoscale for production
- Minimize document size (RUs scale with size)
- Use point reads instead of queries when possible
- Avoid cross-partition queries
- Use Time-to-Live (TTL) to automatically delete old data
- Consider reserved capacity for predictable workloads (up to 65% savings)

---
[Back to Overview](./OVERVIEW.md)
