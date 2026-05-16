# Container and Database Architecture

### Database vs Container Throughput

**Database-level throughput (shared)**:
- RU/s shared across all containers in the database
- Minimum 100 RU/s per container, 400 RU/s total minimum
- Cost-effective for many small containers with variable load
- **Risk**: One hot container can starve others

**Container-level throughput (dedicated)**:
- Each container has isolated RU/s allocation
- Predictable performance per container
- Required for containers needing more than 10,000 RU/s dedicated
- Higher total cost when running many containers

### Container Design

Single container when:
- Documents share the same partition key strategy
- Documents are queried together frequently
- TTL policies align across document types
- Indexing requirements are similar

Separate containers when:
- Partition key strategies differ
- Throughput requirements differ significantly
- TTL requirements differ
- Security boundaries require isolation
- Different indexing policies are optimal

### Naming Conventions

- **Databases**: `{application}-{environment}` — `orderservice-prod`, `analytics-staging`
- **Containers**: Plural nouns describing contents — `orders`, `users`, `events`, `auditLogs`
- **Partition key property**: `pk` or descriptive — `tenantId`, `userId`, `deviceId`

### Container Settings

| Immutable (set at creation) | Mutable |
|:----------------------------|:--------|
| Partition key path | Default TTL |
| Unique key constraints | Indexing policy |
| Analytical store enablement | Throughput configuration |

### Unique Key Constraints

Define unique key constraints to enforce uniqueness within a logical partition:
- Compound unique keys: `["/email", "/tenantId"]` ensures unique email per tenant
- Unique keys are partition-scoped; the same value can exist in different partitions
- Cannot be added after container creation
- Null values consume one uniqueness slot per path

---
[Back to Overview](./OVERVIEW.md)
