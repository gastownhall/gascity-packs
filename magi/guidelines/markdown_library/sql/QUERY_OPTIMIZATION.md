# Query Optimization

### Execution Plan Analysis

- Always examine execution plans for queries that run frequently or perform poorly.
- Use `EXPLAIN ANALYZE` (PostgreSQL), `SET STATISTICS IO ON` (SQL Server), or `EXPLAIN FORMAT=JSON` (MySQL).
- Look for sequential scans on large tables, nested loops with high row estimates, sorts without index support.
- Compare estimated vs actual row counts; large discrepancies indicate stale statistics.

```sql
-- PostgreSQL
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT u.email, COUNT(o.id) as order_count
FROM user u
LEFT JOIN order o ON o.user_id = u.id
GROUP BY u.id, u.email;

-- SQL Server
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
SELECT u.email, COUNT(o.id) as order_count
FROM user u
LEFT JOIN order o ON o.user_id = u.id
GROUP BY u.id, u.email;
```

Key execution plan elements to evaluate:

| Element | Good | Investigate |
|:--------|:----:|:-----------:|
| Scan types | Index seek | Table/heap scan on large tables |
| Join types | Hash join (large), nested loops (small), merge join (sorted) | Nested loops on large datasets |
| Sort operations | In-memory | Disk spill |
| Parallelism | DOP > 1 for large operations | Excessive parallelism (resource pressure) |

### Selectivity and Cardinality

- High selectivity predicates (filtering to <5% of rows) benefit most from indexes.
- Low selectivity predicates may perform better with table scans; the optimizer usually knows.
- Statistics must be current; run `ANALYZE` after bulk loads or significant data changes.

### Query Structure Optimization

- Avoid `SELECT *`; select only needed columns to reduce I/O and enable index-only scans.
- Push predicates as close to the source as possible; filter early, not after joins.
- Use `EXISTS` instead of `IN` for correlated subqueries; it short-circuits on first match.
- Replace `DISTINCT` with proper joins or `GROUP BY` when it masks a query design problem.
- Avoid functions on indexed columns in `WHERE` clauses: `WHERE YEAR(created_at) = 2024` cannot use an index on `created_at`.

**Sargable vs non-sargable predicates:**

```sql
-- NON-SARGABLE: Function on column prevents index use
WHERE YEAR(created_at) = 2024

-- SARGABLE: Range predicate uses index
WHERE created_at >= '2024-01-01' AND created_at < '2025-01-01'

-- NON-SARGABLE: Expression on column
WHERE amount * 1.1 > 100

-- SARGABLE: Rewritten with literal
WHERE amount > 100 / 1.1
```

### Join Optimization

- Ensure join columns are indexed on both sides.
- Prefer explicit join syntax over comma-separated tables with `WHERE` conditions.
- Order tables in join sequence to filter early when optimizer hints are needed (rare).
- Avoid joining on expressions or functions; create computed columns with indexes if necessary.

### Pagination

```sql
-- SLOW: Offset pagination at deep offsets
SELECT * FROM log_entry ORDER BY created_at DESC LIMIT 20 OFFSET 100000;

-- FAST: Keyset pagination
SELECT id, email, created_at
FROM user
WHERE created_at < '2024-01-15 10:30:00'  -- Last row from previous page
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

- Offset-based pagination (`LIMIT 20 OFFSET 1000`) degrades at high offsets; database still scans skipped rows.
- Keyset pagination (seek method) scales consistently: `WHERE id > :last_seen_id ORDER BY id LIMIT 20`.
- For user-facing pagination, consider approximate counts; exact `COUNT(*)` on large tables is expensive.

### Batching

- Batch bulk operations into chunks of 1,000–10,000 rows to avoid lock escalation and transaction log bloat.
- Use `INSERT INTO ... SELECT` for server-side bulk operations; avoid round-trips.
- Batch deletes and updates with indexed predicates; **never `DELETE FROM table` without a `WHERE` clause in production**.

### Query Hints

Use sparingly and document justification:

| Hint | Use |
|:-----|:----|
| `OPTION (RECOMPILE)` | Queries with highly variable parameters |
| `OPTION (MAXDOP 1)` | Prevent parallelism for queries where it hurts |
| `OPTION (FORCE ORDER)` | Optimizer join order is suboptimal |
| `WITH (INDEX(...))` | Force specific index use |

```sql
-- SQL Server: Force index use (use only with documented justification)
SELECT * FROM purchase_order WITH (INDEX(ix_order_created_at))
WHERE created_at >= '2024-01-01'
OPTION (RECOMPILE);

-- PostgreSQL: Disable specific plan types (session-level)
SET enable_seqscan = off;  -- Force index usage
SET enable_nestloop = off;  -- Prevent nested loops

-- MySQL: Index hints
SELECT u.email, o.total_amount
FROM user u
INNER JOIN order o USE INDEX (ix_order_user_id) ON o.user_id = u.id;
```

---
[Back to Overview](./OVERVIEW.md)
