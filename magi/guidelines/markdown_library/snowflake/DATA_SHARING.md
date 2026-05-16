# Data Sharing and Marketplace

### Direct Data Sharing

Share data without copying between Snowflake accounts:

```sql
-- Provider account
CREATE SHARE customer_data_share;
GRANT USAGE ON DATABASE analytics_db TO SHARE customer_data_share;
GRANT USAGE ON SCHEMA analytics_db.reporting TO SHARE customer_data_share;
GRANT SELECT ON TABLE analytics_db.reporting.customer_summary TO SHARE customer_data_share;
ALTER SHARE customer_data_share ADD ACCOUNTS = consumer_account_locator;

-- Consumer account
CREATE DATABASE shared_customer_data FROM SHARE provider_account.customer_data_share;
```

### Share Architecture

Shares are **read-only references** to provider data. Consumers:

- Query live data (no stale copies).
- Pay only for their compute.
- Cannot modify shared objects.
- See data subject to provider's row/column security policies.

### Secure Views for Sharing

```sql
CREATE SECURE VIEW analytics_db.sharing.v_customer_public AS
SELECT 
    customer_id,
    region,
    segment,
    -- Exclude PII
    total_orders,
    lifetime_value
FROM analytics_db.core.customer;

GRANT SELECT ON VIEW analytics_db.sharing.v_customer_public TO SHARE customer_share;
```

Secure views hide underlying query logic from consumers.

### Snowflake Marketplace

| Listing | Use case |
|:--------|:---------|
| Free | Lead generation, public data |
| Paid | Revenue-generating data products |
| Private | Specific customer data delivery |

Marketplace listings require data profile documentation and Snowflake approval.

### Reader Accounts

Create managed accounts for consumers without Snowflake:

```sql
CREATE MANAGED ACCOUNT consumer_reader
    ADMIN_NAME = 'admin'
    ADMIN_PASSWORD = '...'
    TYPE = READER;

ALTER SHARE data_share ADD ACCOUNTS = consumer_reader;
```

**You pay for their compute** — size warehouses accordingly.

### Cross-Region and Cross-Cloud Sharing

```sql
-- Primary region
ALTER DATABASE analytics_db ENABLE REPLICATION TO ACCOUNTS consumer_org.consumer_account;

-- Secondary region (consumer)
CREATE DATABASE analytics_db_replica AS REPLICA OF primary_org.primary_account.analytics_db;
```

Replication incurs data transfer costs. Use for compliance, disaster recovery, or cross-region consumer access requirements.

---
[Back to Overview](./OVERVIEW.md)
