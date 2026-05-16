# Dynamic Tables

Dynamic Tables provide declarative data transformation pipelines with automated materialization and refresh based on a target lag.

```sql
CREATE DYNAMIC TABLE dt_customer_summary
    TARGET_LAG = '1 HOUR'
    WAREHOUSE = transform_wh
AS
SELECT
    customer_id,
    COUNT(*) as order_count,
    SUM(order_total) as lifetime_value,
    MAX(order_date) as last_order_date
FROM orders
GROUP BY customer_id;
```

| Parameter | Description |
|:----------|:------------|
| `TARGET_LAG` | Maximum staleness tolerance (e.g., `'1 HOUR'`, `'10 MINUTES'`, `DOWNSTREAM`) |
| `WAREHOUSE` | Compute resource for refresh |

### Monitoring

Monitor refreshes via `DYNAMIC_TABLE_REFRESH_HISTORY`:

- Refresh duration
- Credits consumed
- Lag measured against `TARGET_LAG`

Dynamic tables are an alternative to manually orchestrated stream + task pipelines when the freshness requirement can be expressed as a target lag and the SQL is fully declarative.

---
[Back to Overview](./OVERVIEW.md)
