# Time Travel and Fail-Safe

### Time Travel Configuration

```sql
-- Query historical state
SELECT * FROM sales AT (TIMESTAMP => '2025-01-14 10:00:00'::TIMESTAMP);
SELECT * FROM sales AT (OFFSET => -60*60);  -- 1 hour ago
SELECT * FROM sales BEFORE (STATEMENT => 'query-id-here');

-- Restore deleted table
UNDROP TABLE accidentally_dropped;

-- Clone from historical point
CREATE TABLE sales_backup CLONE sales AT (TIMESTAMP => '2025-01-14 00:00:00'::TIMESTAMP);
```

### Retention Configuration

| Edition | Maximum Retention |
|:--------|:-----------------:|
| Standard | 1 day |
| Enterprise+ | 90 days |

Configure per-table:

```sql
ALTER TABLE critical_data SET DATA_RETENTION_TIME_IN_DAYS = 30;
ALTER TABLE staging_data SET DATA_RETENTION_TIME_IN_DAYS = 0;  -- Disable
```

| Table type | Retention | Justification |
|:-----------|:---------:|:--------------|
| Critical | 30–90 days | Compliance and recovery |
| Standard | 7–14 days | Operational recovery |
| Staging | 0–1 day | Reproducible from source |

**Longer retention increases storage costs.** Set retention based on recovery requirements, not maximum available.

### Fail-Safe

Fail-safe provides **7 additional days** of data protection after Time Travel expires. Fail-safe data:

- Is **not queryable by users**.
- Can only be recovered by Snowflake support.
- Exists only for permanent tables (not transient/temporary).

Fail-safe is disaster recovery insurance, not an operational feature.

### Storage Cost Implications

Time Travel and Fail-safe incur storage costs for changed data:

- Initial load: base storage cost.
- Updates/deletes: historical versions stored for retention period.
- Fail-safe: changed data stored for additional 7 days.

High-churn tables (frequent updates) accumulate significant historical storage. Consider transient tables for frequently rebuilt data, reduced retention for non-critical tables, periodic TRUNCATE-and-reload vs incremental updates for full-refresh scenarios.

---
[Back to Overview](./OVERVIEW.md)
