# Monitoring and Diagnostics

### Key Metrics

- **Query performance**: Execution time, reads, writes, CPU time per query.
- **Wait statistics**: Lock waits, I/O waits, memory waits indicate bottlenecks.
- **Connection usage**: Active connections, pool utilization, failed connection attempts.
- **Transaction behavior**: Long-running transactions, rollback rate, deadlock frequency.
- **Replication health**: Lag time, replication errors, synchronization status.

### Slow Query Logging

- Enable slow query logging with threshold appropriate to workload (100ms–1s).
- Capture execution plans for slow queries.
- Aggregate and analyze slow query patterns; fix systemic issues, not individual queries.
- Retain slow query logs for trend analysis.

```sql
-- PostgreSQL: Enable slow query logging
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- Log queries over 1 second
SELECT pg_reload_conf();

-- Find slow queries
SELECT
    query,
    calls,
    total_time,
    mean_time,
    max_time,
    stddev_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 20;

-- SQL Server: Query Store
ALTER DATABASE mydb SET QUERY_STORE = ON;
SELECT TOP 10
    q.query_id,
    qt.query_text_id,
    qt.query_sql_text,
    SUM(rs.count_executions) AS total_executions,
    AVG(rs.avg_duration) AS avg_duration
FROM sys.query_store_query q
JOIN sys.query_store_query_text qt ON q.query_text_id = qt.query_text_id
JOIN sys.query_store_runtime_stats rs ON q.query_id = rs.query_id
GROUP BY q.query_id, qt.query_text_id, qt.query_sql_text
ORDER BY avg_duration DESC;
```

### Health Checks

```sql
-- Simple health check query
SELECT 1 AS health_check;

-- Health check with replication lag (PostgreSQL)
SELECT
    CASE WHEN pg_is_in_recovery()
        THEN EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))
        ELSE 0
    END AS replication_lag_seconds;
```

### Alerting

- Alert on connection pool exhaustion before it causes failures.
- Alert on query time percentile degradation (p95, p99).
- Alert on replication lag exceeding acceptable thresholds.
- Alert on disk space utilization; database disk full is catastrophic.
- Alert on long-running transactions (> 5 minutes for OLTP).
- Alert on deadlock frequency spikes.

### Query Store / Performance Schema

- Enable Query Store (SQL Server) or `pg_stat_statements` (PostgreSQL) for query performance history.
- Review regressed queries after deployments.
- Use captured plans for baseline comparison.

```sql
-- PostgreSQL: Enable pg_stat_statements
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Find top queries by total time
SELECT
    calls,
    total_exec_time / 1000 AS total_seconds,
    mean_exec_time AS avg_ms,
    query
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;
```

### Operational Telemetry Additions

Track and alert on:

- Autovacuum lag (PostgreSQL) or maintenance backlog (engine-specific).
- Index bloat / table bloat (PostgreSQL) or fragmentation (SQL Server).
- Transaction log growth rate and log backup latency (SQL Server) / WAL growth and archival health (PostgreSQL).
- Checkpoint pressure and I/O saturation.

Ensure database logs and performance telemetry are centralized and retained long enough to debug slow regressions (at least weeks, ideally months).

### Extended Events / Profiling

```sql
-- SQL Server Extended Events for query performance
CREATE EVENT SESSION query_performance ON SERVER
ADD EVENT sqlserver.sql_statement_completed (
    ACTION (sqlserver.sql_text, sqlserver.database_name)
    WHERE duration > 1000000  -- 1 second
)
ADD TARGET package0.event_file (SET filename = 'query_performance.xel');
```

---
[Back to Overview](./OVERVIEW.md)
