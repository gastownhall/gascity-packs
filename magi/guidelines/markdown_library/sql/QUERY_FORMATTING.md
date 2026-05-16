# Query Formatting and Structure

### Line Length and Layout

- **Maximum line length**: 200 characters.
- **Keyword capitalization**: ALL CAPS for SQL keywords: `SELECT`, `FROM`, `WHERE`, `JOIN`, `INSERT`, `UPDATE`, `DELETE`.
- **Indentation**: 4 spaces per nesting level; no tabs.

### SELECT Statement Structure

```sql
SELECT
    u.id,
    u.email_address,
    u.created_at,
    COUNT(o.id) AS order_count,
    COALESCE(SUM(o.total_amount), 0) AS lifetime_value
FROM app_user u
LEFT JOIN purchase_order o ON o.user_id = u.id AND o.status = 'completed'
WHERE u.is_active = TRUE
    AND u.created_at >= '2024-01-01'
GROUP BY u.id, u.email_address, u.created_at
HAVING COUNT(o.id) > 0
ORDER BY lifetime_value DESC
LIMIT 100;
```

#### Column Lists

- One column per line for queries with more than three columns.
- Always qualify column names with table aliases in multi-table queries.
- Use meaningful aliases: `AS order_count`, not `AS cnt` or `AS c`.
- Trailing commas are prohibited; place commas at the start of continuation lines for clean diffs if preferred by team convention.

#### Table Aliases

- Use short, meaningful aliases derived from table names: `u` for `user`, `oi` for `order_item`, `pt` for `payment_transaction`.
- Never use single letters that don't correlate to the table: `a`, `b`, `c` as arbitrary aliases are prohibited.
- Self-joins require descriptive aliases: `parent`, `child`, `manager`, `employee`.

#### Subqueries and Derived Tables

- Always alias derived tables.
- Indent subquery contents one level.
- Complex subqueries that exceed 20 lines should become CTEs or views.

#### Compact Queries

Simple queries may remain on fewer lines when under 200 characters total:

```sql
SELECT id, email_address, created_at FROM app_user WHERE is_active = TRUE ORDER BY created_at DESC;
```

### INSERT Statement Structure

```sql
INSERT INTO app_user (
    email_address,
    password_hash,
    created_at,
    is_active
)
VALUES (
    'user@example.com',
    '$2b$12$...',
    CURRENT_TIMESTAMP,
    TRUE
);
```

For multi-row inserts:

```sql
INSERT INTO product_category (name, sort_order)
VALUES
    ('Electronics', 1),
    ('Clothing', 2),
    ('Books', 3);
```

### UPDATE Statement Structure

```sql
UPDATE purchase_order
SET
    status = 'shipped',
    shipped_at = CURRENT_TIMESTAMP,
    updated_at = CURRENT_TIMESTAMP
WHERE id = @order_id
    AND status = 'processing';
```

**Always include a `WHERE` clause. Always verify row count expectations before executing.**

### DELETE Statement Structure

```sql
DELETE FROM session_token
WHERE expires_at < CURRENT_TIMESTAMP
    AND is_revoked = FALSE;
```

**Never execute `DELETE FROM table;` without a `WHERE` clause in production.**

### MERGE / UPSERT

```sql
-- PostgreSQL
INSERT INTO product_inventory (product_id, warehouse_id, quantity)
VALUES (@product_id, @warehouse_id, @quantity)
ON CONFLICT (product_id, warehouse_id)
DO UPDATE SET
    quantity = product_inventory.quantity + EXCLUDED.quantity,
    updated_at = CURRENT_TIMESTAMP;

-- PostgreSQL bulk upsert
INSERT INTO inventory (product_id, quantity)
VALUES (1, 100), (2, 200), (3, 300)
ON CONFLICT (product_id)
DO UPDATE SET quantity = EXCLUDED.quantity;

-- SQL Server
MERGE INTO product_inventory AS target
USING (SELECT @product_id AS product_id, @warehouse_id AS warehouse_id, @quantity AS quantity) AS source
ON target.product_id = source.product_id AND target.warehouse_id = source.warehouse_id
WHEN MATCHED THEN
    UPDATE SET quantity = target.quantity + source.quantity, updated_at = GETUTCDATE()
WHEN NOT MATCHED THEN
    INSERT (product_id, warehouse_id, quantity, created_at)
    VALUES (source.product_id, source.warehouse_id, source.quantity, GETUTCDATE());
```

> SQL Server `MERGE` has known edge cases with concurrent operations; prefer explicit `UPDATE` + `INSERT` in high-contention scenarios.

### Bulk Operations

```sql
-- Bulk update with CASE
UPDATE product
SET price = CASE id
    WHEN 1 THEN 19.99
    WHEN 2 THEN 29.99
    WHEN 3 THEN 39.99
    END,
    updated_at = NOW()
WHERE id IN (1, 2, 3);
```

### Comment Conventions

```sql
-- Single-line comment for brief explanations

/*
 * Multi-line comment for complex logic.
 * Explain WHY, not WHAT the code does.
 */

-- TODO: [TICKET-123] Refactor this query when new index is available
```

Comments should explain business logic, not SQL syntax. If you need to explain what a query does, it's too complex.

---
[Back to Overview](./OVERVIEW.md)
