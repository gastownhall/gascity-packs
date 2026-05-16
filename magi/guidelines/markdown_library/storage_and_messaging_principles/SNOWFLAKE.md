# Snowflake

### What It Is

Snowflake is a cloud data warehouse designed for analytical workloads. It separates storage and compute, enabling independent scaling, and provides near-unlimited concurrency for analytics queries.

### When to Consider Snowflake

- Data warehouse/analytics workloads
- Separating OLTP from OLAP
- Complex analytical queries over large datasets
- Multi-cloud data strategy
- Data sharing across organizations
- Semi-structured data analytics (JSON, Parquet)

### Comparison with Synapse Analytics

| Aspect          | Snowflake                | Synapse Analytics         |
|-----------------|--------------------------|---------------------------|
| Cloud           | Multi-cloud              | Azure-native              |
| Pricing         | Per-second compute       | Provisioned or serverless |
| Concurrency     | Excellent                | Good (with scaling)       |
| Semi-structured | Excellent (VARIANT type) | Good (JSON support)       |
| Ecosystem       | Third-party integrations | Azure-native integrations |
| Data Sharing    | Built-in marketplace     | Via Data Share service    |

### When NOT to Use Snowflake

- OLTP workloads requiring low-latency writes
- Real-time data (better with streaming + Snowflake)
- Simple queries against small datasets
- Cost-sensitive scenarios with unpredictable usage
- Tight Azure-native integration requirements

### Integration Pattern

```
OLTP (SQL Server) → CDC → Event Hubs → Stream Processing → Snowflake (Analytics)
                                              ↓
                              Real-time dashboards (Power BI, Looker)
```

---
[Back to Overview](./OVERVIEW.md)
