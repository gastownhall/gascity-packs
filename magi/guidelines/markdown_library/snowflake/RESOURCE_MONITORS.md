# Resource Monitors and Cost Management

### Resource Monitor Configuration

```sql
CREATE RESOURCE MONITOR monthly_budget
    WITH CREDIT_QUOTA = 10000
    FREQUENCY = MONTHLY
    START_TIMESTAMP = IMMEDIATELY
    TRIGGERS
        ON 75 PERCENT DO NOTIFY
        ON 90 PERCENT DO NOTIFY
        ON 100 PERCENT DO SUSPEND
        ON 110 PERCENT DO SUSPEND_IMMEDIATE;

ALTER WAREHOUSE analytics_wh SET RESOURCE_MONITOR = monthly_budget;
```

| Action | Behavior |
|:-------|:---------|
| `NOTIFY` | Send alert to account admins |
| `SUSPEND` | Prevent new queries; allow running queries to complete |
| `SUSPEND_IMMEDIATE` | Kill running queries immediately |

### Monitor Assignment

Assign monitors to specific warehouses or account-wide:

```sql
ALTER WAREHOUSE analytics_wh SET RESOURCE_MONITOR = monthly_budget;
ALTER ACCOUNT SET RESOURCE_MONITOR = account_budget;
```

### Cost Attribution

| Approach | Mechanism |
|:---------|:----------|
| Warehouse-level | Query `WAREHOUSE_METERING_HISTORY` for compute credits by warehouse |
| Query-level | Aggregate `QUERY_HISTORY` by warehouse, user, or tagged dimensions |
| Tag-based | Apply tags to warehouses, queries, and objects; correlate with billing data |

### Cost Optimization Levers

| Lever | Tactics |
|:------|:--------|
| Warehouse | Right-size based on query performance analysis; aggressive auto-suspend (60s default); multi-cluster for concurrency, not single-query speed |
| Storage | Transient tables for reproducible data; appropriate Time Travel retention; drop unused tables and clones |
| Query | Avoid full table scans on large tables; leverage result caching; materialized views for repeated expensive aggregations |
| Serverless | Monitor `AUTOMATIC_CLUSTERING_HISTORY`, `PIPE_USAGE_HISTORY`, `SEARCH_OPTIMIZATION_HISTORY`, `QUERY_ACCELERATION_HISTORY` |

### Billing and Usage Views

| View | Purpose |
|:-----|:--------|
| `WAREHOUSE_METERING_HISTORY` | Warehouse credits consumed |
| `AUTOMATIC_CLUSTERING_HISTORY` | Reclustering credits |
| `PIPE_USAGE_HISTORY` | Snowpipe credits |
| `SEARCH_OPTIMIZATION_HISTORY` | Search optimization credits |
| `STORAGE_USAGE` | Storage bytes billed |

Build dashboards tracking these metrics weekly.

---
[Back to Overview](./OVERVIEW.md)
