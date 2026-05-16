# Query Optimization

### Query Fundamentals

Every query reports RU consumption in the response headers. **This is the primary metric for query efficiency.** A query returning the same results can cost 5 RU or 5,000 RU depending on how it's written.

### Single-Partition Queries

Always prefer single-partition queries:
```sql
SELECT * FROM c WHERE c.pk = "tenant-123" AND c.type = "Order"
```

The SDK and query engine recognize partition key filters and route to a single partition. **Cross-partition queries fan out to all partitions, multiplying RU cost and latency.**

### Cross-Partition Query Avoidance

If queries frequently need data across partitions, **the partition key design is wrong.** Revisit the data model before accepting cross-partition queries as normal.

When cross-partition queries are unavoidable:
- Enable parallel execution with `MaxConcurrency`
- Accept increased RU consumption
- Monitor and budget for the cost

### Projection

Select only needed properties:
```sql
SELECT c.id, c.status, c.total FROM c WHERE c.pk = "tenant-123"
```

**Avoid `SELECT *` in production code.** Unused properties consume network bandwidth and client memory.

### Pagination

Use continuation tokens for large result sets:
```csharp
var query = container.GetItemQueryIterator<Order>(queryDefinition,
    requestOptions: new QueryRequestOptions { MaxItemCount = 100 });
while (query.HasMoreResults)
{
    var response = await query.ReadNextAsync();
    // Process response.Resource
    // response.ContinuationToken for next page
}
```

Set `MaxItemCount` to balance latency (smaller pages return faster) against throughput (fewer round trips).

### Filtering Efficiency

**Efficient** — filters on indexed properties:
```sql
SELECT * FROM c WHERE c.pk = "tenant-123" AND c.status = "active"
```

**Inefficient** — functions on properties prevent index use:
```sql
SELECT * FROM c WHERE c.pk = "tenant-123" AND LOWER(c.email) = "user@example.com"
```

Store pre-computed values (lowercase email) if case-insensitive filtering is required.

### Aggregations

Aggregations (`COUNT`, `SUM`, `AVG`, `MIN`, `MAX`) execute within the database:
```sql
SELECT COUNT(1) AS orderCount, SUM(c.total) AS totalRevenue
FROM c WHERE c.pk = "tenant-123" AND c.type = "Order"
```

Aggregations still incur RU proportional to documents scanned. Large aggregations may timeout; **use the Change Feed for materialized aggregates.**

### JOIN Semantics

Cosmos DB `JOIN` is an **intra-document** join, not inter-document:
```sql
SELECT c.id, item.productId, item.quantity
FROM c
JOIN item IN c.items
WHERE c.pk = "tenant-123" AND c.type = "Order"
```

This flattens arrays within documents. **There is no join between documents** — that's what embedding and denormalization solve.

### Subqueries

```sql
SELECT * FROM c
WHERE c.pk = "tenant-123"
AND EXISTS (SELECT VALUE item FROM item IN c.items WHERE item.quantity > 10)
```

### Query Plan Analysis

Use `QueryMetrics` to understand query execution:
- `RetrievedDocumentCount` — documents read from storage
- `OutputDocumentCount` — documents returned after filtering
- High ratio indicates post-index filtering; **improve indexes**
- `IndexLookupTime`, `DocumentLoadTime`, `RuntimeExecutionTime` identify bottlenecks

---
[Back to Overview](./OVERVIEW.md)
