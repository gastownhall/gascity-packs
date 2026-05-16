# Partition Key Design

### Partition Key Fundamentals

The partition key determines:
- Which physical partition stores the document
- The boundary for transactions (stored procedures, transactional batch)
- Query efficiency (single-partition vs cross-partition)
- Throughput distribution across physical partitions
- Maximum throughput per logical partition (10,000 RU/s)

### Selection Criteria

An ideal partition key:
- Has high cardinality (many distinct values)
- Distributes requests evenly (no hot partitions)
- Appears in the `WHERE` clause of most queries
- Groups related documents that are queried together
- Has values known at write time without additional lookups

### Common Partition Key Patterns

| Pattern | Use case | Notes |
|:--------|:---------|:------|
| **Tenant ID** | Multi-tenant applications | All tenant data colocates; tenants isolated from each other's hot partitions |
| **User ID** | User-centric applications | User data retrieved in single-partition queries; user-level transactions |
| **Device ID / Entity ID** | IoT and event-driven systems | Time-series data for a device stays together |
| **Synthetic Key** | When no natural property satisfies | `{region}_{customerId}` or hash-based distribution |
| **Hierarchical** | Multi-level access patterns (up to 3 levels) | `tenantId/userId/orderId` enables queries at any level |

### Anti-Patterns

- **Low cardinality keys** — partitioning by `status`, `country`, or `category` creates few partitions with uneven distribution
- **Timestamp as partition key** — creates hot partitions at the current time; historical data becomes cold partitions that still consume provisioned throughput
- **Random/UUID partition keys** — distributes writes but makes queries expensive; every query becomes cross-partition unless querying by exact ID
- **Partition key not in query predicates** — every query fans out to all partitions

### Partition Key Immutability

Partition keys cannot be changed after document creation. To "change" a partition key:
1. Create a new document with the new partition key value
2. Delete the old document
3. Handle the transactional implications (not atomic across partitions)

**Design partition keys to never require change.** If business requirements might change the key value, that property is not a suitable partition key.

### Logical Partition Limits

| Limit | Value |
|:------|:------|
| Maximum storage per logical partition | 20 GB |
| Maximum RU/s per logical partition | 10,000 |

Monitor partition sizes; approaching limits requires data redistribution or model changes.

---
[Back to Overview](./OVERVIEW.md)
