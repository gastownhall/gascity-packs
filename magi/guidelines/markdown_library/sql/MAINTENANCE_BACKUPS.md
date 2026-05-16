# Maintenance, Backups, and Recovery

### Backups Are Only Real If Restore Works

- Backups must be automated, monitored, and **restore-tested**.
- Define and document:
  - **RPO (Recovery Point Objective)**: maximum acceptable data loss window.
  - **RTO (Recovery Time Objective)**: maximum acceptable time to restore service.
- Test restores on a schedule (for example, monthly) using production-like size and encryption settings.
- For engines that support point-in-time recovery (PITR):
  - Ensure log/WAL backups and retention are configured.
  - Periodically validate PITR by restoring to a specific timestamp.

### Backup Strategy

| Tier | Cadence |
|:-----|:--------|
| Full backups | Weekly or daily depending on database size and RPO |
| Differential backups | Daily (SQL Server); contain changes since last full |
| Transaction log backups | Every 5–15 minutes for production OLTP systems |
| Continuous archiving | PostgreSQL WAL archiving or SQL Server log shipping for minimal RPO |

### Backup Hygiene

- Encrypt backups at rest.
- Store backups in separate failure domains.
- Rotate backup encryption keys and access credentials under a documented process.
- Alert on:
  - Failed backup jobs.
  - Missing backup artifacts beyond expected cadence.
  - Backup size anomalies.

### Routine Maintenance

| Engine | Maintenance |
|:-------|:------------|
| **PostgreSQL** | Ensure autovacuum is functional and not starved; monitor bloat and vacuum lag; run `ANALYZE` after bulk changes; monitor for transaction ID wraparound |
| **SQL Server** | Monitor index fragmentation; update statistics; run `DBCC CHECKDB` regularly; manage log file growth |
| **MySQL/InnoDB** | Monitor buffer pool, slow query log, replication; validate query patterns avoid long-running transactions; `OPTIMIZE TABLE` for fragmented tables |
| **SQLite** | Use WAL mode; periodically run `VACUUM` only when justified; monitor file size |

```sql
-- PostgreSQL maintenance
VACUUM ANALYZE user;  -- Update statistics and reclaim space
REINDEX TABLE user;   -- Rebuild indexes

-- SQL Server maintenance
UPDATE STATISTICS user WITH FULLSCAN;
DBCC INDEXDEFRAG (mydb, user);

-- Monitor table bloat (PostgreSQL)
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    n_live_tup,
    n_dead_tup,
    n_dead_tup * 100.0 / NULLIF(n_live_tup + n_dead_tup, 0) AS dead_percentage
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000
ORDER BY n_dead_tup DESC;
```

### Index Maintenance

```sql
-- SQL Server: Evaluate fragmentation
SELECT
    OBJECT_NAME(i.object_id) AS table_name,
    i.name AS index_name,
    ps.avg_fragmentation_in_percent,
    ps.page_count
FROM sys.dm_db_index_physical_stats(DB_ID(), NULL, NULL, NULL, 'LIMITED') ps
JOIN sys.indexes i ON ps.object_id = i.object_id AND ps.index_id = i.index_id
WHERE ps.avg_fragmentation_in_percent > 10 AND ps.page_count > 1000;
```

| Fragmentation | Action |
|:-------------:|:-------|
| 10–30% | `ALTER INDEX ... REORGANIZE` |
| > 30% | `ALTER INDEX ... REBUILD` (`ONLINE = ON` if possible) |

```sql
-- PostgreSQL: Reindex
REINDEX INDEX CONCURRENTLY ix_table_column;  -- PostgreSQL 12+
```

### Capacity Planning and Growth

Track growth rates for primary data size, index size, transaction logs/WAL, I/O and CPU utilization at p95/p99. **Running out of disk is a high-severity, avoidable incident.**

### Database Shrink Warning

**Never shrink database files in normal operations:**

- Shrinking causes massive fragmentation.
- I/O patterns become random, destroying performance.
- The space will likely be needed again.
- If you need to reclaim space, plan a maintenance window with full rebuild afterward.

The only acceptable shrink scenarios:

- One-time space reclamation after major data deletion (archiving, purging).
- Followed immediately by index rebuild and statistics update.

---
[Back to Overview](./OVERVIEW.md)
