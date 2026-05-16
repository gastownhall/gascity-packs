# Monitoring and Observability

### Account Usage Views

`SNOWFLAKE.ACCOUNT_USAGE` provides rich operational data with **45-minute latency**:

```sql
-- Top expensive queries
SELECT 
    query_id,
    query_text,
    warehouse_name,
    total_elapsed_time / 1000 as seconds,
    bytes_scanned / POWER(1024, 3) as gb_scanned,
    credits_used_cloud_services
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time > DATEADD(HOUR, -24, CURRENT_TIMESTAMP())
ORDER BY total_elapsed_time DESC
LIMIT 100;

-- Warehouse credit consumption
SELECT 
    warehouse_name,
    DATE_TRUNC('HOUR', start_time) as hour,
    SUM(credits_used) as credits
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE start_time > DATEADD(DAY, -7, CURRENT_TIMESTAMP())
GROUP BY 1, 2
ORDER BY 1, 2;

-- Failed login attempts
SELECT 
    user_name,
    client_ip,
    reported_client_type,
    first_authentication_factor,
    is_success,
    error_message
FROM SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY
WHERE event_timestamp > DATEADD(DAY, -1, CURRENT_TIMESTAMP())
AND is_success = 'NO';
```

### Information Schema (Real-Time)

`INFORMATION_SCHEMA` provides real-time data but with session/warehouse scope:

```sql
SELECT * FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY_BY_WAREHOUSE(
    WAREHOUSE_NAME => 'ANALYTICS_WH',
    END_TIME_RANGE_START => DATEADD(HOUR, -1, CURRENT_TIMESTAMP())
));
```

### Query Tagging

```sql
ALTER SESSION SET QUERY_TAG = 'dbt_daily_run';
-- Subsequent queries tagged
-- Query tags appear in QUERY_HISTORY
```

Use tags for application identification, cost attribution by feature/team, debug session correlation.

### Alert Configuration

```sql
CREATE ALERT high_credit_usage
    WAREHOUSE = monitoring_wh
    SCHEDULE = '1 HOUR'
    IF (EXISTS (
        SELECT 1 FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
        WHERE start_time > DATEADD(HOUR, -1, CURRENT_TIMESTAMP())
        GROUP BY warehouse_name
        HAVING SUM(credits_used) > 100
    ))
    THEN CALL send_alert_notification('High credit usage detected');
```

### Key Metrics to Track

| Category | Metrics |
|:---------|:--------|
| Cost | Daily/weekly credit consumption by warehouse; storage growth rate; serverless feature credit consumption |
| Performance | Query execution time percentiles (p50, p90, p99); bytes scanned per query; spillage to local/remote storage; queue time for concurrent queries |
| Security | Failed login attempts; privilege escalations; data access anomalies |

---
[Back to Overview](./OVERVIEW.md)
