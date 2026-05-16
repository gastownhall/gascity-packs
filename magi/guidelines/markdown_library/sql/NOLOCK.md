# NOLOCK and Read Uncommitted

### What NOLOCK Does

The `NOLOCK` hint (SQL Server) or `READ UNCOMMITTED` isolation level allows queries to read data without acquiring shared locks. This means:

- Queries can read rows that are currently being modified by other transactions.
- Queries can read rows that will be rolled back (dirty reads).
- Queries can see inconsistent data if rows move during the scan (phantom reads).
- Queries can read the same row twice or skip rows entirely due to page splits.

### When NOLOCK Is Acceptable

- **Approximate counts are sufficient**: Dashboard widgets showing "~10,000 active users" where ±5% is acceptable.
- **Stale data is explicitly acceptable**: Reporting on yesterday's data where today's in-flight transactions don't matter.
- **The query is read-only and non-critical**: Background analytics, trend analysis, monitoring queries.
- **Write activity is minimal or non-existent**: Queries against archive tables or read replicas.
- **The alternative is unacceptable blocking**: When shared locks would block critical writes unacceptably.

### When NOLOCK Is Prohibited

- **Data accuracy matters**: Financial calculations, inventory checks, balance inquiries.
- **Decisions will be made on the result**: Order processing, authorization checks, rate limiting.
- **The query feeds into writes**: Reading data that will be updated or used as input to INSERT/UPDATE.
- **Consistency with other queries matters**: Multiple queries that must see the same snapshot.
- **Foreign key lookups are involved**: Parent/child relationships may appear inconsistent.
- **Aggregations require accuracy**: SUM, AVG, COUNT where precision matters.

### NOLOCK Anti-Patterns

```sql
-- PROHIBITED: Using NOLOCK for transactional reads
SELECT @balance = balance FROM account WITH (NOLOCK) WHERE id = @account_id;
IF @balance >= @withdrawal_amount
    -- Race condition: balance may have changed or been rolled back

-- PROHIBITED: Using NOLOCK for data that feeds writes
INSERT INTO order_item (product_id, price)
SELECT id, current_price FROM product WITH (NOLOCK) WHERE id = @product_id;
-- Price may be a rolled-back value

-- PROHIBITED: Using NOLOCK for existence checks
IF EXISTS (SELECT 1 FROM subscription WITH (NOLOCK) WHERE user_id = @user_id AND status = 'active')
    -- Subscription may not actually exist if transaction rolls back

-- PROHIBITED: Using NOLOCK to "fix" blocking problems
-- This masks the real issue: missing indexes, long transactions, or poor design
```

### Correct NOLOCK Usage

```sql
-- ACCEPTABLE: Dashboard count that tolerates approximation
SELECT COUNT(*) AS approximate_user_count
FROM app_user WITH (NOLOCK)
WHERE is_active = 1;

-- ACCEPTABLE: Reporting query on historical data
SELECT
    DATE(created_at) AS order_date,
    COUNT(*) AS order_count,
    SUM(total_amount) AS daily_total
FROM purchase_order WITH (NOLOCK)
WHERE created_at < DATEADD(DAY, -1, GETDATE())  -- Yesterday and earlier
GROUP BY DATE(created_at);

-- ACCEPTABLE: Monitoring query that's sampling system state
SELECT TOP 100 *
FROM slow_query_log WITH (NOLOCK)
ORDER BY duration_ms DESC;
```

### Alternatives to NOLOCK

Before reaching for NOLOCK, consider:

| Alternative | Behavior |
|:------------|:---------|
| Snapshot Isolation | Consistent reads without blocking; no inconsistency risks of NOLOCK |
| Read Committed Snapshot Isolation (RCSI) | Database-level setting that changes READ COMMITTED to use row versioning |
| Read replicas | Route read-heavy reporting queries to replicas |
| Optimized indexes | Often, NOLOCK is a band-aid for missing indexes; add covering or filtered indexes |
| Query optimization | Reduce query duration to minimize lock hold time |

```sql
-- Snapshot isolation
SET TRANSACTION ISOLATION LEVEL SNAPSHOT;
BEGIN TRANSACTION;
SELECT * FROM large_table;  -- Consistent snapshot, no blocking
COMMIT;

-- RCSI
ALTER DATABASE MyDatabase SET READ_COMMITTED_SNAPSHOT ON;
```

### NOLOCK Equivalents in Other Databases

```sql
-- PostgreSQL uses MVCC by default; dirty reads are not possible
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;  -- Same as READ COMMITTED in PostgreSQL

-- MySQL InnoDB
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
SELECT * FROM large_table;
COMMIT;
```

### NOLOCK Documentation Requirements

Every query using NOLOCK must be documented with:

1. **Justification**: Why dirty reads are acceptable.
2. **Accuracy tolerance**: What level of inaccuracy is acceptable.
3. **Review date**: When this decision should be re-evaluated.
4. **Owner**: Who approved this usage.

```sql
/*
 * NOLOCK Justification: Dashboard user count widget
 * Accuracy tolerance: ±10% acceptable for display purposes
 * Review date: 2025-06-01
 * Approved by: Database team (JIRA-12345)
 */
SELECT COUNT(*) FROM app_user WITH (NOLOCK) WHERE is_active = 1;
```

---
[Back to Overview](./OVERVIEW.md)
