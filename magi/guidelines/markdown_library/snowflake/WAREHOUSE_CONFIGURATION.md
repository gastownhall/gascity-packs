# Virtual Warehouse Configuration

### Warehouse Sizing

Each warehouse size doubles resources (and cost) from the previous:

| Size | Credits/Hour | Relative Capacity | Use case |
|:-----|:------------:|:-----------------:|:---------|
| X-Small | 1 | 1× | Light queries, development |
| Small | 2 | 2× | Standard analytics queries |
| Medium | 4 | 4× | Complex queries, moderate concurrency |
| Large | 8 | 8× | Heavy ETL, large scans |
| X-Large | 16 | 16× | Massive transformations |
| 2X-Large | 32 | 32× | Enterprise ETL |
| 3X-Large | 64 | 64× | Extreme workloads |
| 4X-Large | 128 | 128× | Maximum parallelism |

**Right-sizing principle:** start small, measure query performance, scale up only when queries are bottlenecked on compute. A 10-second query on X-Small that becomes 5 seconds on Small costs the same in credits but ties up warehouse resources longer.

### Auto-Suspend Configuration

```sql
CREATE WAREHOUSE analytics_wh
    WAREHOUSE_SIZE = 'MEDIUM'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE;
```

| Workload | Auto-suspend |
|:---------|:------------:|
| Interactive workloads | 60–300s |
| Scheduled batch jobs | 60s |
| **`AUTO_SUSPEND = 0`** | **Never** — runs continuously, burning credits |

### Multi-Cluster Warehouses (Enterprise+)

```sql
CREATE WAREHOUSE concurrent_wh
    WAREHOUSE_SIZE = 'MEDIUM'
    MIN_CLUSTER_COUNT = 1
    MAX_CLUSTER_COUNT = 4
    SCALING_POLICY = 'STANDARD';
```

| Scaling policy | Behavior |
|:---------------|:---------|
| `STANDARD` | Favor query performance; add clusters when queuing detected |
| `ECONOMY` | Favor cost; add clusters only after sustained queuing |

Use multi-cluster for **highly concurrent workloads** (many simultaneous users/queries). **Don't use multi-cluster when queries are individually slow** — that's a sizing problem, not a concurrency problem.

### Workload Isolation

Create dedicated warehouses for distinct workloads:

| Warehouse | Purpose | Suggested size |
|:----------|:--------|:--------------:|
| `etl_wh` | Data loading and transformation; batch throughput | Large |
| `analytics_wh` | Ad-hoc analyst queries | Medium |
| `bi_wh` | BI tool queries | Small–Medium |
| `dbt_wh` | dbt transformations | Medium |

Isolation provides independent scaling per workload, cost attribution by warehouse, protection from noisy neighbors, and workload-specific tuning.

### Query Acceleration Service

Enterprise feature that offloads eligible query portions to serverless compute:

```sql
ALTER WAREHOUSE analytics_wh SET 
    ENABLE_QUERY_ACCELERATION = TRUE
    QUERY_ACCELERATION_MAX_SCALE_FACTOR = 4;
```

Effective for queries with large scans that benefit from parallelism and selective filters that enable partial acceleration. Not a replacement for proper warehouse sizing. Monitor costs via `QUERY_ACCELERATION_HISTORY`.

### Warehouse Tagging for Cost Attribution

```sql
ALTER WAREHOUSE analytics_wh SET TAG cost_center = 'marketing';
ALTER WAREHOUSE etl_wh SET TAG cost_center = 'data_engineering';

-- Query costs by tag
SELECT
    OBJECT_GET_TAG('cost_center', 'WAREHOUSE', warehouse_name) as cost_center,
    SUM(credits_used) as total_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
GROUP BY 1;
```

---
[Back to Overview](./OVERVIEW.md)
