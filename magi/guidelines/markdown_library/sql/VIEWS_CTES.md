# Views and Common Table Expressions

### View Use Cases

- Encapsulating complex joins for simplified querying by applications.
- Providing consistent filtered access (active records, soft-delete exclusion).
- Abstracting schema changes from dependent queries.
- Row-level security through views exposing filtered data.

### View Standards

- Name views descriptively: `v_active_user`, `v_order_summary`, `v_product_inventory`.
- Document the purpose and any filtering applied.
- Avoid nesting views deeply; views calling views calling views become performance nightmares.
- Understand view performance characteristics: simple views inline; complex views may materialize.

### Updatable Views

Views can be updatable when:

- Single table with no aggregations.
- No `DISTINCT`, `GROUP BY`, `HAVING`.
- All columns mapped directly to base table.
- Consider `INSTEAD OF` triggers for complex update logic.

### Materialized Views

- Use materialized views for expensive aggregations or joins queried frequently.
- Define refresh strategy: on-demand, scheduled, or incremental (where supported).
- Index materialized views for query patterns.
- Monitor refresh time and storage costs.

```sql
-- PostgreSQL materialized view
CREATE MATERIALIZED VIEW mv_user_order_summary AS
SELECT
    u.id AS user_id,
    u.email_address,
    COUNT(o.id) AS order_count,
    COALESCE(SUM(o.total_amount), 0) AS lifetime_value
FROM app_user u
LEFT JOIN purchase_order o ON o.user_id = u.id AND o.status = 'completed'
GROUP BY u.id, u.email_address;

CREATE INDEX ix_mv_user_order_summary_user_id ON mv_user_order_summary (user_id);

-- Refresh the materialized view
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_user_order_summary;
```

### Common Table Expressions (CTEs)

```sql
WITH recent_orders AS (
    SELECT user_id, COUNT(*) AS order_count, SUM(total_amount) AS total_spent
    FROM purchase_order
    WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY user_id
)
SELECT u.email_address, ro.order_count, ro.total_spent
FROM app_user u
INNER JOIN recent_orders ro ON ro.user_id = u.id
ORDER BY ro.total_spent DESC;
```

#### CTE vs Subquery vs Temp Table

| Choice | When |
|:-------|:-----|
| **CTE** | Readability, single-query scope, recursive queries; may be inlined or materialized by optimizer |
| **Subquery** | Simple cases; avoid deep nesting |
| **Temp table** | Multi-statement logic requiring intermediate results; explicit statistics for optimizer |

```sql
-- CTE for simple one-time use
WITH recent_orders AS (
    SELECT user_id, SUM(total_amount) as total_spent
    FROM order
    WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY user_id
)
SELECT u.email, ro.total_spent
FROM user u
INNER JOIN recent_orders ro ON ro.user_id = u.id;

-- Temp table for complex multi-use
CREATE TEMP TABLE user_metrics AS
SELECT
    user_id,
    COUNT(*) as order_count,
    SUM(total_amount) as total_spent,
    MAX(created_at) as last_order_date
FROM order
WHERE created_at >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY user_id;
CREATE INDEX ix_temp_user_metrics ON user_metrics(user_id);
-- Use multiple times
SELECT * FROM user_metrics WHERE order_count > 10;
SELECT AVG(total_spent) FROM user_metrics;
```

#### CTE Materialization Hints

PostgreSQL 12+ allows materialization hints:

```sql
WITH expensive_calculation AS MATERIALIZED (
    -- Force the CTE to materialize
    SELECT ...
)
SELECT ...;

WITH cheap_calculation AS NOT MATERIALIZED (
    -- Allow the optimizer to inline
    SELECT ...
)
SELECT ...;
```

### Recursive CTEs

Use for hierarchical data: organizational trees, category hierarchies, graph traversal. **Always include a termination condition and limit recursion depth to prevent infinite loops.**

```sql
WITH RECURSIVE category_tree AS (
    -- Anchor: top-level categories
    SELECT id, name, parent_id, 0 AS depth
    FROM category
    WHERE parent_id IS NULL

    UNION ALL

    -- Recursive: child categories
    SELECT c.id, c.name, c.parent_id, ct.depth + 1
    FROM category c
    INNER JOIN category_tree ct ON ct.id = c.parent_id
    WHERE ct.depth < 10  -- Prevent infinite recursion
)
SELECT * FROM category_tree ORDER BY depth, name;
```

---
[Back to Overview](./OVERVIEW.md)
