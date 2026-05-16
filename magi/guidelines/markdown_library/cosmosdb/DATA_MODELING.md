# Data Modeling Strategy

### Denormalization Principles

Relational normalization minimizes storage duplication at the cost of joins. Cosmos DB has **no joins across documents**. The tradeoff inverts: duplicate data to eliminate multi-document reads.

**Embed when**:
- Data is queried together in the same operation
- Child entities have no independent lifecycle
- Child entity count is bounded and small (under 100 items)
- Update frequency of embedded data is low

**Reference when**:
- Data is queried independently
- Child entities have independent lifecycle (created, updated, deleted separately)
- Child entity count is unbounded or large
- Embedded data would cause document size to approach 2MB limit
- Update frequency would cause excessive RU consumption from full document rewrites

### Embedding Example

```json
{
  "id": "order-123",
  "pk": "customer-456",
  "items": [
    { "productId": "prod-1", "quantity": 2, "price": 19.99 },
    { "productId": "prod-2", "quantity": 1, "price": 39.99 }
  ],
  "shippingAddress": {
    "street": "123 Main St",
    "city": "Seattle",
    "postalCode": "98101"
  }
}
```

### Document Structure

Required:
- `id` — unique within the partition; string type; immutable after creation
- Partition key property — the property designated as partition key; immutable after creation
- `_etag` — system-generated; used for optimistic concurrency
- `_ts` — system-generated; Unix timestamp of last modification

Recommended:
- `type` — discriminator for polymorphic containers holding multiple entity types
- `createdAt` — ISO 8601 timestamp of creation
- `updatedAt` — ISO 8601 timestamp of last modification
- `createdBy` — actor identifier for audit
- `ttl` — time-to-live in seconds when applicable

### Document Size Management

| Threshold | Treatment |
|:----------|:----------|
| 2 MB | **Hard limit** including system properties and indexing overhead |
| 100 KB | Target for optimal performance |
| 500 KB | Reconsider model; split into multiple documents |

Large documents consume more RUs for reads and writes.

### Polymorphic Containers

Multiple entity types can coexist in a single container when they share a partition key and benefit from unified querying:

```json
{
  "id": "user-123",
  "pk": "tenant-abc",
  "type": "User",
  "email": "user@example.com",
  "name": "Jane Doe"
}

{
  "id": "order-456",
  "pk": "tenant-abc",
  "type": "Order",
  "userId": "user-123",
  "total": 99.99,
  "items": [...]
}
```

Filter by `type` in queries to retrieve specific entity types. Include `type` in composite indexes used by entity-specific queries.

### Reference Patterns

When references are necessary, store the referenced document's `id` and partition key:

```json
{
  "id": "order-456",
  "pk": "tenant-abc",
  "type": "Order",
  "customer": {
    "id": "user-123",
    "pk": "tenant-abc",
    "name": "Jane Doe"
  }
}
```

Include frequently-read properties of the referenced entity to avoid secondary lookups. Accept that this data may become stale; implement update propagation for properties that require consistency.

### Array Management

Arrays embedded in documents have performance implications:

- Arrays over **100 items** degrade query performance when filtering array elements
- Array modifications require full document replacement (read-modify-write)
- Unbounded arrays eventually hit the 2MB document limit
- Consider separate documents for large or frequently-modified collections

---
[Back to Overview](./OVERVIEW.md)
