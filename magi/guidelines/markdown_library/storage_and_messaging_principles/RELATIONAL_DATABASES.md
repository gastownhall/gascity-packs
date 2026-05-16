# Relational Databases (SQL Server, PostgreSQL, MySQL)

### What They Are

Relational databases store data in tables with rows and columns, enforce schemas, support ACID transactions, and use SQL for querying. They excel at structured data with complex relationships, strong consistency requirements, and ad-hoc query needs.

### Core Strengths

- **ACID Transactions**: Atomicity, Consistency, Isolation, Durability guarantee data integrity across complex operations
- **Strong Consistency**: Reads always return the most recent committed write
- **Complex Queries**: JOINs, aggregations, window functions, CTEs enable sophisticated data retrieval
- **Schema Enforcement**: The database enforces data structure; invalid data is rejected at write time
- **Mature Tooling**: Decades of tooling for backup, monitoring, optimization, and administration
- **Referential Integrity**: Foreign keys prevent orphaned records and maintain relationship validity

### Core Weaknesses

- **Horizontal Scaling**: Scaling writes across multiple nodes is complex (sharding, partitioning)
- **Schema Rigidity**: Schema changes require migrations; adding columns to billion-row tables is expensive
- **Geographic Distribution**: Multi-region deployments with strong consistency are complex and latency-sensitive
- **Document Storage**: Storing hierarchical or semi-structured data requires JSON columns or normalization

### Ideal Use Cases

- Transactional systems requiring ACID guarantees (orders, payments, inventory)
- Data with complex relationships requiring JOINs (users, organizations, permissions)
- Applications requiring strong consistency (financial, compliance, audit)
- Systems with complex reporting and ad-hoc query requirements
- Multi-tenant applications with row-level security requirements
- Any system where data integrity is paramount

### Avoid When

- Data has no relationships and access is purely by primary key
- Write throughput exceeds what a single node can handle (>50K writes/second sustained)
- Schema changes frequently (weekly or more)
- Geographic distribution with low-latency requirements across regions
- Data is inherently hierarchical/nested (documents within documents)

### Scale Boundaries

- Single node: Up to ~10TB data, ~10K transactions/second for typical workloads
- With read replicas: Higher read throughput, same write throughput
- With sharding: Higher write throughput, but query complexity increases dramatically
- Cloud managed services (Azure SQL, RDS, Cloud SQL): Easier scaling, higher cost

### Cost Model

- Compute (vCores, memory) + Storage (GB) + I/O (in some providers)
- Reserved capacity for predictable workloads reduces cost significantly
- Read replicas multiply compute cost
- Backup storage adds 10-20% to storage costs typically

---
[Back to Overview](./OVERVIEW.md)
