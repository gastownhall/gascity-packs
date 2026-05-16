# Joins and Relationships

### Join Types

| Type | Behavior |
|:-----|:---------|
| `INNER JOIN` | Returns rows with matches in both tables; default for most relationships |
| `LEFT JOIN` | All rows from left table, NULLs for non-matching right rows; optional relationships |
| `RIGHT JOIN` | Inverted left join; **avoid for readability**, reorder tables instead |
| `FULL OUTER JOIN` | All rows from both tables; rare in practice, expensive |
| `CROSS JOIN` | Cartesian product; explicit only when generating combinations |

### Join Syntax

Always use explicit JOIN syntax with ON conditions:

```sql
SELECT o.id, u.email_address
FROM purchase_order o
INNER JOIN app_user u ON u.id = o.user_id
WHERE o.status = 'completed';
```

**Never use implicit joins with comma-separated tables:**

```sql
-- PROHIBITED
SELECT o.id, u.email_address
FROM purchase_order o, app_user u
WHERE o.user_id = u.id AND o.status = 'completed';
```

### Join Condition Placement

Place join conditions in the `ON` clause, not the `WHERE` clause:

```sql
-- CORRECT: Filter on join condition
SELECT o.id, u.email_address
FROM purchase_order o
LEFT JOIN app_user u ON u.id = o.user_id AND u.is_active = TRUE
WHERE o.status = 'completed';

-- DIFFERENT BEHAVIOR: Filter after join (may exclude rows unexpectedly)
SELECT o.id, u.email_address
FROM purchase_order o
LEFT JOIN app_user u ON u.id = o.user_id
WHERE o.status = 'completed'
    AND u.is_active = TRUE;  -- This converts LEFT JOIN to INNER JOIN behavior
```

### Self-Joins

```sql
SELECT e.name AS employee, m.name AS manager
FROM employee e
LEFT JOIN employee m ON m.id = e.manager_id;
```

### Many-to-Many Relationships

Junction tables require:

- Composite primary key on both foreign keys, or surrogate key with unique constraint on the pair.
- Indexes on each foreign key column for efficient lookups in both directions.
- Additional columns for relationship metadata (`created_at`, `role`, `rank`) when applicable.

```sql
CREATE TABLE user_role (
    user_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    granted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    granted_by INTEGER,
    CONSTRAINT pk_user_role PRIMARY KEY (user_id, role_id),
    CONSTRAINT fk_user_role_user FOREIGN KEY (user_id) REFERENCES app_user (id) ON DELETE CASCADE,
    CONSTRAINT fk_user_role_role FOREIGN KEY (role_id) REFERENCES role (id) ON DELETE CASCADE
);

CREATE INDEX ix_user_role_role_id ON user_role (role_id);
```

### Anti-Join Patterns

To find rows without matches in another table, use `NOT EXISTS` or `LEFT JOIN ... WHERE IS NULL`:

```sql
-- Users without orders (NOT EXISTS)
SELECT u.id, u.email_address
FROM app_user u
WHERE NOT EXISTS (
    SELECT 1 FROM purchase_order o WHERE o.user_id = u.id
);

-- Users without orders (LEFT JOIN)
SELECT u.id, u.email_address
FROM app_user u
LEFT JOIN purchase_order o ON o.user_id = u.id
WHERE o.id IS NULL;
```

`NOT IN` with nullable columns returns unexpected results; **avoid it**:

```sql
-- DANGEROUS if purchase_order.user_id can be NULL
SELECT u.id FROM app_user u
WHERE u.id NOT IN (SELECT user_id FROM purchase_order);
```

### Semi-Join Patterns

```sql
-- Users WITH orders (EXISTS is typically more efficient than DISTINCT + JOIN)
SELECT u.id, u.email_address
FROM app_user u
WHERE EXISTS (
    SELECT 1 FROM purchase_order o WHERE o.user_id = u.id
);
```

### Lateral Joins (PostgreSQL) / CROSS APPLY (SQL Server)

For row-by-row correlated subqueries:

```sql
-- PostgreSQL: Get latest order for each user
SELECT u.id, u.email_address, lo.id AS latest_order_id, lo.created_at
FROM app_user u
LEFT JOIN LATERAL (
    SELECT o.id, o.created_at
    FROM purchase_order o
    WHERE o.user_id = u.id
    ORDER BY o.created_at DESC
    LIMIT 1
) lo ON TRUE;

-- SQL Server: Equivalent using CROSS APPLY
SELECT u.id, u.email_address, lo.id AS latest_order_id, lo.created_at
FROM app_user u
OUTER APPLY (
    SELECT TOP 1 o.id, o.created_at
    FROM purchase_order o
    WHERE o.user_id = u.id
    ORDER BY o.created_at DESC
) lo;
```

### Window Functions

Window functions are essential for analytics, ranking, and running calculations.

```sql
-- Row numbering
SELECT
    id,
    email,
    ROW_NUMBER() OVER (ORDER BY created_at DESC) as row_num
FROM user;

-- Running totals
SELECT
    order_date,
    total_amount,
    SUM(total_amount) OVER (
        ORDER BY order_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) as running_total
FROM order;

-- Ranking within groups
SELECT
    department_id,
    employee_name,
    salary,
    RANK() OVER (PARTITION BY department_id ORDER BY salary DESC) as salary_rank
FROM employee;
```

---
[Back to Overview](./OVERVIEW.md)
