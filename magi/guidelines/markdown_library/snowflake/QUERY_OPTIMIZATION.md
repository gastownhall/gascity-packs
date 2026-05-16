# Query Optimization

### Query Profile Analysis

**Every query should have its profile examined before optimization.** The Query Profile in the Snowflake UI reveals:

- Execution plan with operator costs.
- Partition pruning effectiveness.
- Spilling to local/remote storage.
- Join strategies selected.
- Time spent per operation.

### Partition Pruning

Pruning eliminates micro-partitions from scans based on filter predicates. Pruning works when:

- Filter predicates use constants or deterministic expressions.
- Predicates align with clustering keys or natural data ordering.
- No functions wrap the filtered column.

```sql
-- Pruning-friendly
SELECT * FROM events WHERE event_date = '2025-01-15';
SELECT * FROM events WHERE event_date BETWEEN '2025-01-01' AND '2025-01-31';

-- Pruning-defeated
SELECT * FROM events WHERE DATE(event_timestamp) = '2025-01-15';  -- Function on column
SELECT * FROM events WHERE event_date = CURRENT_DATE();  -- Non-deterministic

-- Pruning OK (function on constant evaluated at compile time)
SELECT * FROM events WHERE event_type = UPPER('purchase');
```

Add computed columns for common filter transformations and cluster on them.

### Join Optimization

Snowflake automatically selects join strategies. Help the optimizer by:

- Joining on columns with declared relationships (constraints with `RELY`).
- Filtering early — predicates in `WHERE` before or during join, not after.
- Ensuring join columns have compatible types (implicit casts disable optimizations).

Snowflake reorders joins automatically. **Trust the optimizer** unless Query Profile shows suboptimal plans, then consider explicit join hints (rare).

### Materialized Views

```sql
CREATE MATERIALIZED VIEW mv_daily_sales AS
SELECT 
    sale_date,
    product_id,
    SUM(quantity) as total_quantity,
    SUM(revenue) as total_revenue
FROM sales
GROUP BY sale_date, product_id;
```

Materialized views automatically refresh when base data changes (serverless compute cost) and are automatically used by the query optimizer when beneficial. **Don't create speculatively** — identify expensive, frequent queries first.

### Result Caching

Snowflake caches query results for **24 hours**. Identical queries return cached results instantly with zero compute cost. Caching works when:

- Query text is identical (including whitespace).
- Underlying data hasn't changed.
- User has access to the result.

Design applications to benefit from caching: consistent query formatting, parameterize user-specific elements only where necessary, consider pre-warming caches for critical dashboards.

### Search Optimization Service

Enterprise feature for point lookup queries:

```sql
ALTER TABLE customers ADD SEARCH OPTIMIZATION ON EQUALITY(customer_id, email);
```

Effective for high-cardinality equality filters and queries seeking individual records in large tables. Adds storage overhead and maintenance cost. **Enable selectively for proven use cases.**

### Common Query Anti-Patterns

| Anti-pattern | Issue | Fix |
|:-------------|:------|:----|
| `SELECT *` | Defeats columnar storage | Select only needed columns |
| `DISTINCT` without thought | Often masks join issues | Fix the query, don't bandage |
| `ORDER BY` without `LIMIT` | Sorts entire result set | Add `LIMIT` |
| Unnecessary subqueries | Complexity without benefit | Flatten to JOINs |
| Functions in `WHERE` on filtered columns | Prevents pruning | Precompute values or restructure |

---
[Back to Overview](./OVERVIEW.md)
