# Transactions and Stored Procedures

### Transaction Boundaries

Transactions in Cosmos DB are **limited to a single logical partition**. Cross-partition transactions are not supported. This fundamental constraint drives partition key design.

### Transactional Batch (SDK)

For client-side transaction orchestration:
- Up to 100 operations per batch
- Maximum 2MB total request size
- All operations on same partition key
- Atomic: all succeed or all fail

### Stored Procedures

Server-side JavaScript execution within a partition:
- Atomic transactions with ACID guarantees
- Bounded execution time (5 seconds default)
- Access limited to single partition
- Useful for complex conditional logic that would require multiple round trips

Appropriate for:
- Complex validation before writes
- Conditional updates based on current state
- Batch operations requiring atomicity

Avoid for:
- Simple CRUD operations (SDK is simpler)
- Operations spanning partitions (impossible)
- Complex business logic better suited to application code

### Triggers

- **Pre-triggers**: execute before an operation; can modify the document
- **Post-triggers**: execute after an operation; can perform additional actions

Triggers add latency and complexity. Prefer application-side logic or Change Feed processing.

### User-Defined Functions

JavaScript functions callable from queries:
```sql
SELECT c.id, udf.formatCurrency(c.total) AS formattedTotal FROM c WHERE c.pk = "tenant-123"
```

UDFs add query complexity and execution time. Prefer pre-computed values stored in documents.

---
[Back to Overview](./OVERVIEW.md)
