# Development and Deployment Patterns

### Infrastructure as Code

**Terraform** (Snowflake provider):

```hcl
resource "snowflake_database" "analytics" {
  name                        = "ANALYTICS_DB"
  data_retention_time_in_days = 30
}

resource "snowflake_warehouse" "etl" {
  name           = "ETL_WH"
  warehouse_size = "MEDIUM"
  auto_suspend   = 60
  auto_resume    = true
}
```

**Schemachange / Flyway** (SQL migrations):

```text
migrations/
    V001__create_database.sql
    V002__create_schemas.sql
    V003__create_tables.sql
    V004__add_indexes.sql
```

### CI/CD Integration

Standard deployment pipeline:

1. Developer creates feature branch.
2. SQL changes reviewed in pull request.
3. CI runs linting and validation.
4. Merge to main triggers deployment to dev environment.
5. Promotion to staging/prod through environment pipelines.

### dbt Integration

dbt is the standard for transformation orchestration.

**Model configuration:**

```sql
{{ config(
    materialized='incremental',
    unique_key='order_id',
    cluster_by=['order_date'],
    snowflake_warehouse='TRANSFORM_WH'
) }}

SELECT ...
FROM {{ ref('stg_orders') }}
{% if is_incremental() %}
WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
{% endif %}
```

### Environment Isolation

| Approach | Isolation | Use case |
|:---------|:---------:|:---------|
| Separate accounts | Strongest | `acme_analytics_dev` / `staging` / `prod` |
| Database-level | Strong | `analytics_dev_db` / `analytics_staging_db` / `analytics_prod_db` |
| Schema-level | Minimal | `analytics_db.dev_*` / `staging_*` / `prod_*` |

### Zero-Copy Cloning for Development

```sql
-- Clone production for testing
CREATE DATABASE analytics_dev_db CLONE analytics_prod_db;

-- Clone specific schema
CREATE SCHEMA test_schema CLONE prod_schema;

-- Clone table with Time Travel
CREATE TABLE test_table CLONE prod_table
  AT (TIMESTAMP => DATEADD(DAY, -1, CURRENT_TIMESTAMP()));
```

Clones are **instant and consume no additional storage** until data diverges.

### Blue-Green Deployment Pattern

```sql
-- Deploy new version to inactive schema
CREATE SCHEMA analytics_db.v2 CLONE analytics_db.v1;
-- Apply migrations to v2; validate v2

-- Swap active schema
ALTER SCHEMA analytics_db.v1 RENAME TO analytics_db.v1_deprecated;
ALTER SCHEMA analytics_db.v2 RENAME TO analytics_db.v1;
```

Applications reference stable schema name; underlying version changes atomically.

---
[Back to Overview](./OVERVIEW.md)
