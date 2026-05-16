# Core Principles

These guidelines define strict, performant, and cost-effective patterns for Azure Cosmos DB implementations, optimizing for:

- **Partition-Aware Design**: Every data model decision acknowledges partition boundaries; cross-partition operations are exceptional, not normal
- **Request Unit Economy**: RU consumption is a first-class design constraint; queries and operations are evaluated by their RU cost, not just correctness
- **Denormalization by Default**: Data is modeled for read patterns, not relational purity; duplication is a feature, not a bug
- **Consistency Intentionality**: Consistency level is chosen per-operation based on requirements, not defaulted globally and forgotten
- **Horizontal Scale Mindset**: Design assumes millions of documents and terabytes of data from day one; patterns that work at small scale but fail at large scale are rejected

### Primary Rule: Model for Your Access Patterns

Cosmos DB is not a relational database. Trying to use it like one produces expensive, slow, unmaintainable systems. Before writing a single document schema, enumerate every read and write pattern the application requires. The data model exists to serve those patterns efficiently, not to represent abstract entity relationships.

### Secondary Rule: Partition Key Is Destiny

The partition key decision is the most consequential architectural choice in Cosmos DB. It determines query efficiency, throughput distribution, transaction boundaries, and cost characteristics. **A bad partition key cannot be fixed without data migration.** Invest heavily in getting it right before writing data.

### API Selection

These guidelines assume the **NoSQL (formerly SQL) API** unless otherwise noted. The NoSQL API provides the richest feature set and most flexible querying. Other APIs:

| API | Use case |
|:----|:---------|
| **NoSQL (default)** | New workloads; richest features and flexible querying |
| MongoDB | Migrating existing MongoDB workloads with minimal code changes |
| Cassandra | Existing Cassandra expertise or wide-column requirements |
| Gremlin | Graph traversal queries as primary access pattern |
| Table | Simple key-value with Azure Table Storage migration path |

Choose the API that matches your team's expertise and access patterns. **Don't choose MongoDB API just because "MongoDB is popular"** — the NoSQL API is more capable.

---
[Back to Overview](./OVERVIEW.md)
