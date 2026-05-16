# Clustering and Micro-Partitioning

### Micro-Partition Fundamentals

Snowflake automatically partitions data into micro-partitions (50–500MB compressed) during ingestion. Each micro-partition stores:

- Columnar data with compression.
- Min/max values per column.
- Distinct value counts.
- Null counts.

The query optimizer uses this metadata for **partition pruning** — eliminating partitions that cannot contain matching rows without scanning them.

### Natural Clustering

Data loads naturally cluster by ingestion order. If you load time-series data chronologically, timestamp columns cluster effectively without intervention. Queries filtering on timestamp ranges benefit from natural clustering automatically.

### Explicit Clustering Keys

Define clustering keys when:

- Query patterns consistently filter on specific columns.
- Natural clustering doesn't align with query patterns.
- Large tables (multi-TB) show significant pruning inefficiency.

```sql
ALTER TABLE events CLUSTER BY (event_date, event_type);
```

### Clustering Key Selection

Optimal clustering keys have:

- **High cardinality in combination** — enough distinct values to distribute data across partitions.
- **Low cardinality individually** — date columns, status flags, category codes — not UUIDs or high-cardinality IDs.
- **Frequent filter usage** — columns appearing in most query `WHERE` clauses.

Order clustering key columns by:

1. Columns used in equality filters.
2. Columns used in range filters.
3. Columns used in joins (secondary benefit).

**Maximum four columns** in a clustering key. Beyond four, diminishing returns meet increasing maintenance cost.

### Clustering Depth

Monitor clustering quality:

```sql
SELECT SYSTEM$CLUSTERING_DEPTH('database.schema.table');
SELECT SYSTEM$CLUSTERING_INFORMATION('database.schema.table', '(column1, column2)');
```

| Depth | Quality |
|:-----:|:--------|
| 1–2 | Excellent |
| 3–5 | Acceptable |
| 5+ | Poor — consider reclustering |

### Automatic Clustering

Enable automatic reclustering for tables with clustering keys:

```sql
ALTER TABLE events RESUME RECLUSTER;
```

Automatic Clustering runs in the background, consuming **serverless compute credits**. It's not free — monitor costs via `AUTOMATIC_CLUSTERING_HISTORY` view.

### When NOT to Cluster

- Tables under **1TB** rarely benefit from explicit clustering.
- Tables loaded and queried in the same order (natural clustering sufficient).
- Tables with uniform access patterns across all data (no selective filters).
- High-velocity insert tables where reclustering can't keep pace.

Clustering is a maintenance overhead. **Don't cluster speculatively; measure pruning efficiency first.**

---
[Back to Overview](./OVERVIEW.md)
