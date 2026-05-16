# Indexing Strategy

### Index Selection Principles

- Index columns that appear in `WHERE`, `JOIN`, `ORDER BY`, and `GROUP BY` clauses of frequent queries.
- Analyze query patterns before creating indexes; unused indexes consume write resources.
- Composite indexes serve queries filtering on leading columns; **order matters**.
- Covering indexes eliminate table lookups when all selected columns are in the index.

### Primary Key Indexes

- Primary keys are automatically indexed in all major databases.
- Clustered index (SQL Server, MySQL InnoDB) determines physical row order; choose wisely for range scans.
- In PostgreSQL, primary key index is a regular B-tree; consider `CLUSTER` command for physical ordering.
- Avoid wide primary keys (long strings, multi-column composites) as the clustered index key; every secondary index copies it.

### Composite Index Design

- Place high-selectivity columns first (columns that filter out the most rows).
- Place equality conditions before range conditions: `(status, created_at)` not `(created_at, status)`.
- Include columns used in `ORDER BY` at the end to enable index-only sorts.
- Limit composite indexes to 4–5 columns; beyond that, reconsider query design.

```sql
-- Query: WHERE status = 'active' AND created_at >= '2024-01-01' ORDER BY priority DESC
-- Optimal index: equality column first, then range, then sort
CREATE INDEX ix_task_status_created_priority ON task (status, created_at, priority DESC);

-- Match query predicates
-- For: WHERE user_id = ? AND status = ? ORDER BY created_at DESC
CREATE INDEX ix_order_user_status_created
ON order(user_id, status, created_at DESC);
```

### Covering Indexes (Included Columns)

Covering indexes include non-key columns to satisfy queries without table lookups:

```sql
-- SQL Server
CREATE INDEX ix_order_user_id ON purchase_order (user_id)
INCLUDE (status, total_amount, created_at);

-- PostgreSQL (11+)
CREATE INDEX ix_order_user_id ON purchase_order (user_id)
INCLUDE (status, total_amount, created_at);

-- Filtered covering index (SQL Server)
CREATE INDEX ix_order_user_status_include_total
ON order(user_id, status)
INCLUDE (total_amount, created_at)
WHERE status IN ('pending', 'processing');
```

Use covering indexes when:

- A query frequently selects specific columns with the same filter.
- Table is wide and full row retrieval is expensive.
- The included columns are not useful for filtering/sorting (otherwise make them key columns).

### Partial Indexes

- Create partial indexes for queries that consistently filter a subset: `WHERE is_active = TRUE`.
- Partial indexes reduce storage and improve write performance.
- Document the filter condition prominently; partial indexes are invisible to queries without matching predicates.

```sql
-- PostgreSQL partial index
CREATE INDEX ix_user_active_email ON app_user (email_address) WHERE is_active = TRUE;

-- PostgreSQL with multiple filter conditions
CREATE INDEX ix_user_email_active
ON user(email)
WHERE is_active = true AND deleted_at IS NULL;

-- SQL Server filtered index
CREATE INDEX ix_user_active_email ON app_user (email_address) WHERE is_active = 1;
```

### Index Types

| Type | Best for |
|:-----|:---------|
| B-tree | Default; equality and range queries |
| Hash | Equality-only lookups; rarely advantageous over B-tree in modern databases |
| GIN/GiST | Full-text search, array containment, geometric data, JSONB queries |
| BRIN | Large tables with naturally ordered data (time-series); minimal storage, range-based filtering |
| Columnstore | Analytical workloads with aggregations over many rows; not for OLTP |
| Spatial | R-tree-based indexes for geographic queries |
| Bitmap | Oracle; useful for low-cardinality columns in data warehouse scenarios |

### Columnstore Indexes

For analytical queries on large datasets:

- SQL Server: `CREATE CLUSTERED COLUMNSTORE INDEX` for data warehouse fact tables.
- SQL Server: `CREATE NONCLUSTERED COLUMNSTORE INDEX` for hybrid OLTP/analytics.
- PostgreSQL: Consider TimescaleDB or ClickHouse for true columnar analytics.
- Batch-mode execution provides significant aggregation speedups.

### Full-Text Indexes

- SQL Server: Full-text catalogs with `CONTAINS` and `FREETEXT` predicates.
- PostgreSQL: `tsvector` columns with GIN indexes; `to_tsvector()` and `to_tsquery()`.
- MySQL: `FULLTEXT` indexes on InnoDB.
- Consider dedicated search engines (Elasticsearch, Meilisearch) for complex search requirements.

### Index Maintenance

- Monitor index usage statistics; drop indexes with zero reads and ongoing writes.
- Rebuild fragmented indexes periodically in SQL Server; PostgreSQL handles this via autovacuum.
- Avoid indexing columns with high write frequency unless read patterns demand it.
- Test index changes in non-production environments under realistic load.
- Duplicate indexes waste resources: `(a, b)` makes a standalone `(a)` index redundant.

```sql
-- PostgreSQL: Find unused indexes
SELECT schemaname, relname, indexrelname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0 AND indexrelname NOT LIKE 'pk_%'
ORDER BY pg_relation_size(indexrelid) DESC;

-- PostgreSQL: Monitor index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan;

-- SQL Server: Find unused indexes
SELECT OBJECT_NAME(i.object_id) AS table_name,
       i.name AS index_name,
       s.user_seeks, s.user_scans, s.user_lookups, s.user_updates
FROM sys.indexes i
LEFT JOIN sys.dm_db_index_usage_stats s ON i.object_id = s.object_id AND i.index_id = s.index_id
WHERE OBJECTPROPERTY(i.object_id, 'IsUserTable') = 1
  AND i.type_desc = 'NONCLUSTERED'
  AND (s.user_seeks + s.user_scans + s.user_lookups) = 0
ORDER BY s.user_updates DESC;
```

### Index Anti-Patterns

- Indexing every column "just in case" wastes storage and slows writes.
- Indexing low-cardinality columns (boolean, status with 3 values) rarely helps; query planner often ignores them.
- Redundant indexes: if `(a, b)` exists, a separate `(a)` index is usually unnecessary.
- Missing foreign key indexes: every `_id` column used in joins needs an index on the child table.
- Over-indexing OLTP tables: more than 5–7 indexes per table warrants scrutiny.
- Indexing frequently updated columns without clear read benefit.
- Creating indexes without verifying the query planner uses them.

---
[Back to Overview](./OVERVIEW.md)
