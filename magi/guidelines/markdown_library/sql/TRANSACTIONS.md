# Transactions and Concurrency

### Transaction Principles

- Keep transactions as short as possible; long transactions hold locks and block concurrent operations.
- Never hold transactions open while waiting for user input or external API calls.
- Use explicit transaction boundaries; don't rely on auto-commit behavior for multi-statement operations.
- Commit or rollback every transaction; abandoned transactions leak resources.

### Isolation Levels

| Level | Use |
|:------|:----|
| `READ UNCOMMITTED` | **Never** (dirty reads) |
| `READ COMMITTED` | Default for most applications; sees only committed data, may see non-repeatable reads |
| `REPEATABLE READ` | Consistent snapshot for the transaction duration; prevents non-repeatable reads, may have phantoms |
| `SERIALIZABLE` | Full isolation; expensive, use only for critical financial operations |

Choose the lowest isolation level that meets correctness requirements. Higher isolation increases lock contention and deadlock potential.

```sql
-- Financial transaction requiring serializable
BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;
-- Check balance
SELECT balance FROM account WHERE id = 123 FOR UPDATE;
-- Only proceed if sufficient funds
UPDATE account SET balance = balance - 100 WHERE id = 123;
UPDATE account SET balance = balance + 100 WHERE id = 456;
COMMIT;

-- Report requiring consistent snapshot
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
BEGIN;
-- All queries see same snapshot
SELECT COUNT(*) FROM order WHERE created_at >= '2024-01-01';
SELECT SUM(total_amount) FROM order WHERE created_at >= '2024-01-01';
COMMIT;
```

### Snapshot Isolation

Snapshot isolation (SQL Server) and MVCC (PostgreSQL) provide:

- Readers don't block writers; writers don't block readers.
- Consistent view of data as of transaction start.
- Conflict detection at commit time for concurrent updates.

```sql
-- SQL Server: Enable snapshot isolation at database level
ALTER DATABASE MyDatabase SET ALLOW_SNAPSHOT_ISOLATION ON;
ALTER DATABASE MyDatabase SET READ_COMMITTED_SNAPSHOT ON;  -- Changes READ COMMITTED behavior

-- Using snapshot isolation
SET TRANSACTION ISOLATION LEVEL SNAPSHOT;
BEGIN TRANSACTION;
-- Your queries here
COMMIT;
```

PostgreSQL uses MVCC by default; `REPEATABLE READ` provides similar semantics to SQL Server's snapshot isolation.

### Locking Strategies

- **Optimistic locking**: Version column checked at update time; fails if version changed since read.
- **Pessimistic locking**: `SELECT ... FOR UPDATE` acquires row locks upfront; use for high-contention scenarios.
- **Advisory locks**: Application-level locks for coordinating operations outside row scope.
- Avoid table locks in transactional systems; they serialize all operations.

```sql
-- Optimistic locking pattern
CREATE TABLE product (
    id BIGINT PRIMARY KEY,
    name VARCHAR(255),
    price DECIMAL(19,4),
    version INT NOT NULL DEFAULT 1
);

-- Optimistic update
UPDATE product
SET price = 29.99,
    version = version + 1
WHERE id = 123
AND version = 5;  -- Only updates if version matches
-- Check affected rows in application; if 0 rows affected, retry with fresh data

-- Pessimistic locking pattern
SELECT * FROM product_inventory WHERE id = @inventory_id FOR UPDATE;
-- Row is now locked until transaction completes
UPDATE product_inventory SET quantity = @new_quantity WHERE id = @inventory_id;
COMMIT;
```

### Deadlock Prevention

- Access tables and rows in a consistent order across all code paths.
- Acquire the most contentious locks first.
- Keep transactions short to reduce lock hold time.
- Handle deadlock exceptions with retry logic; deadlocks are normal in concurrent systems.
- **Index foreign keys to prevent table locks.**

```sql
-- Consistent lock ordering
BEGIN;
-- Always lock parent before child
SELECT * FROM user WHERE id = 123 FOR UPDATE;
SELECT * FROM order WHERE user_id = 123 FOR UPDATE;
UPDATE user SET last_order_at = NOW() WHERE id = 123;
COMMIT;

-- Use NOWAIT to fail fast
BEGIN;
SELECT * FROM inventory WHERE product_id = 456 FOR UPDATE NOWAIT;
-- If lock not available, fails immediately instead of waiting
UPDATE inventory SET quantity = quantity - 1 WHERE product_id = 456;
COMMIT;

-- Set lock timeout
SET lock_timeout = '5s';
BEGIN;
UPDATE high_contention_table SET counter = counter + 1 WHERE id = 789;
COMMIT;

-- SQL Server deadlock handling
BEGIN TRY
    -- Transaction logic
END TRY
BEGIN CATCH
    IF ERROR_NUMBER() = 1205  -- Deadlock victim
    BEGIN
        -- Retry logic here
    END
END CATCH
```

### Savepoints

- Use savepoints for partial rollback within a transaction.
- Savepoints enable error recovery without abandoning the entire transaction.
- Release savepoints when no longer needed to free resources.

```sql
-- PostgreSQL savepoint example
BEGIN;
    INSERT INTO order_header (...) VALUES (...);
    SAVEPOINT before_items;

    INSERT INTO order_item (...) VALUES (...);
    -- If this fails, we can rollback just the items
    ROLLBACK TO SAVEPOINT before_items;

    -- Try again or proceed without items
COMMIT;
```

### Lock Monitoring and Diagnosis

```sql
-- SQL Server: Find blocking chains
SELECT
    blocking.session_id AS blocking_session,
    blocked.session_id AS blocked_session,
    blocked.wait_type,
    blocked.wait_time / 1000.0 AS wait_seconds,
    blocking_text.text AS blocking_query,
    blocked_text.text AS blocked_query
FROM sys.dm_exec_requests blocked
INNER JOIN sys.dm_exec_sessions blocking ON blocking.session_id = blocked.blocking_session_id
CROSS APPLY sys.dm_exec_sql_text(blocked.sql_handle) blocked_text
CROSS APPLY sys.dm_exec_sql_text(blocking.most_recent_sql_handle) blocking_text;

-- PostgreSQL: Find blocking queries (rich form)
SELECT
    blocked_locks.pid AS blocked_pid,
    blocked_activity.usename AS blocked_user,
    blocking_locks.pid AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query AS blocked_statement,
    blocking_activity.query AS current_statement_in_blocking_process
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON
    blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
    AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
    AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;

-- Kill blocking session if necessary
SELECT pg_terminate_backend(pid);
```

---
[Back to Overview](./OVERVIEW.md)
