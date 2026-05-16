# Performance Tuning

### Wait Statistics Analysis

```sql
-- SQL Server: Top wait types
SELECT TOP 20
    wait_type,
    wait_time_ms / 1000.0 AS wait_time_seconds,
    waiting_tasks_count,
    wait_time_ms / NULLIF(waiting_tasks_count, 0) AS avg_wait_ms
FROM sys.dm_os_wait_stats
WHERE wait_type NOT IN (
    'CLR_SEMAPHORE', 'LAZYWRITER_SLEEP', 'RESOURCE_QUEUE',
    'SLEEP_TASK', 'SLEEP_SYSTEMTASK', 'SQLTRACE_BUFFER_FLUSH',
    'WAITFOR', 'BROKER_TASK_STOP', 'CHECKPOINT_QUEUE',
    'XE_TIMER_EVENT'  -- Background waits to ignore
)
ORDER BY wait_time_ms DESC;

-- PostgreSQL: Wait event analysis
SELECT wait_event_type, wait_event, COUNT(*) AS count
FROM pg_stat_activity
WHERE state = 'active' AND wait_event IS NOT NULL
GROUP BY wait_event_type, wait_event
ORDER BY count DESC;
```

| Wait type | Remediation |
|:----------|:------------|
| `PAGEIOLATCH_*` | I/O bottleneck; improve storage, add memory, optimize queries |
| `LCK_M_*` | Lock contention; review transaction design, add indexes, consider snapshot isolation |
| `CXPACKET`/`CXCONSUMER` | Parallelism waits; may indicate poor parallel plan distribution |
| `ASYNC_NETWORK_IO` | Application not consuming results fast enough; optimize client code |
| `SOS_SCHEDULER_YIELD` | CPU pressure; optimize queries, add CPU, reduce parallelism |

### Statistics Management

```sql
-- SQL Server: Update statistics for a table
UPDATE STATISTICS purchase_order WITH FULLSCAN;

-- SQL Server: Identify outdated statistics
SELECT
    OBJECT_NAME(s.object_id) AS table_name,
    s.name AS statistic_name,
    sp.last_updated,
    sp.rows,
    sp.modification_counter
FROM sys.stats s
CROSS APPLY sys.dm_db_stats_properties(s.object_id, s.stats_id) sp
WHERE sp.modification_counter > sp.rows * 0.2  -- 20% of rows modified
ORDER BY sp.modification_counter DESC;

-- PostgreSQL: Update statistics
ANALYZE purchase_order;

-- PostgreSQL: Check statistics age
SELECT
    schemaname,
    relname,
    last_analyze,
    last_autoanalyze
FROM pg_stat_user_tables
WHERE last_analyze < CURRENT_DATE - INTERVAL '7 days'
    OR last_analyze IS NULL;
```

### Query Plan Cache Management

```sql
-- SQL Server: Find queries with multiple plans (parameter sniffing issues)
SELECT
    st.text,
    COUNT(*) AS plan_count
FROM sys.dm_exec_query_stats qs
CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) st
GROUP BY st.text
HAVING COUNT(*) > 1
ORDER BY plan_count DESC;
```

### Memory Configuration

| Component | Purpose |
|:----------|:--------|
| Buffer pool | Cache for data pages; larger = fewer disk reads |
| Query memory | Workspace for sorts, hashes, joins; insufficient = disk spills |
| Plan cache | Compiled execution plans; insufficient = recompilation |

```sql
-- SQL Server: Memory usage overview
SELECT
    type,
    pages_kb / 1024 AS memory_mb
FROM sys.dm_os_memory_clerks
WHERE pages_kb > 10240
ORDER BY pages_kb DESC;
```

### TempDB Best Practices (SQL Server)

- Create multiple TempDB data files (1 per CPU core, up to 8).
- Pre-size TempDB files to avoid autogrowth during operations.
- Place TempDB on dedicated fast storage.
- Monitor for PFS, GAM, SGAM contention.
- Avoid large temp table operations in critical paths.

### I/O Tuning

```sql
-- SQL Server: File I/O latency
SELECT
    DB_NAME(database_id) AS database_name,
    file_id,
    io_stall_read_ms / NULLIF(num_of_reads, 0) AS avg_read_latency_ms,
    io_stall_write_ms / NULLIF(num_of_writes, 0) AS avg_write_latency_ms
FROM sys.dm_io_virtual_file_stats(NULL, NULL)
ORDER BY io_stall_read_ms + io_stall_write_ms DESC;
```

| File type | Target latency |
|:----------|:--------------:|
| Data files | < 20ms read, < 5ms write |
| Log files | < 5ms write |
| TempDB | < 10ms read/write |

---
[Back to Overview](./OVERVIEW.md)
