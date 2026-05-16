# Database and Schema Design

### Database Organization

Databases represent logical boundaries for related data. Structure databases by:

| Pattern | Examples |
|:--------|:---------|
| Domain | `sales_db`, `marketing_db`, `finance_db` |
| Layer | `raw_db`, `staging_db`, `curated_db`, `consumption_db` |
| Function | `source_db`, `transform_db`, `analytics_db` |

Avoid monolithic databases containing unrelated domains. Cross-database queries work seamlessly; artificial consolidation provides no benefit and complicates access control.

### Schema Patterns

Within databases, schemas organize objects by purpose:

**Medallion Architecture:**

| Layer | Purpose |
|:------|:--------|
| `bronze` | Raw ingested data, minimal transformation, preserves source fidelity |
| `silver` | Cleansed, conformed, deduplicated data with consistent types |
| `gold` | Business-level aggregates, dimensional models, consumption-ready datasets |

**Functional Separation:**

| Schema | Purpose |
|:-------|:--------|
| `staging` | Temporary landing zone for data loads |
| `core` | Persistent business entities and facts |
| `reporting` | Denormalized views and aggregates for BI tools |
| `sandbox` | Analyst experimentation space with relaxed governance |

**Administrative Schemas:**

| Schema | Purpose |
|:-------|:--------|
| `audit` | Query history, access logs, change tracking |
| `metadata` | Data dictionaries, lineage tables, quality metrics |
| `utils` | Stored procedures, UDFs, shared utilities |

### Naming Conventions

| Object | Style | Example |
|:-------|:------|:--------|
| Databases | `snake_case`, descriptive | `customer_analytics_db` |
| Schemas | `snake_case`, concise | `raw`, `curated`, `reporting` |
| Tables | `snake_case`, singular nouns | `customer`, `order_line_item` |
| Standard views | `v_` prefix | `v_active_users` |
| Materialized views | `mv_` prefix | `mv_daily_sales` |
| Secure views | `sv_` prefix | `sv_customer_pii_masked` |
| Streams | `stream_` prefix | `stream_customer_changes` |
| Tasks | `task_` prefix | `task_daily_aggregation` |
| Stages | `stage_` prefix | `stage_s3_raw_data` |

**Avoid reserved words.** Snowflake is case-insensitive by default; quoted identifiers preserve case but complicate every reference. **Use unquoted lowercase names universally.**

### Schema-Level Defaults

Set defaults at schema creation:

```sql
CREATE SCHEMA analytics.reporting
    WITH MANAGED ACCESS
    DATA_RETENTION_TIME_IN_DAYS = 30
    DEFAULT_DDL_COLLATION = 'en-ci';
```

**`MANAGED ACCESS`** centralizes privilege grants through schema owners, preventing object-level grant proliferation.

---
[Back to Overview](./OVERVIEW.md)
