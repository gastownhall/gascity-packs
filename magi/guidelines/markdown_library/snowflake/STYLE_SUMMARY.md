# Style Summary

| Element | Required Style |
|:--------|:---------------|
| Account Structure | Multi-account for production/staging/dev; single account acceptable for small teams |
| Naming | `snake_case` for all objects; descriptive names; no reserved words |
| Databases | Organized by domain or medallion layer |
| Schemas | Functional separation (staging, core, reporting, audit) |
| Tables | Explicit types; `NOT NULL` where appropriate; constraints declared with `RELY` |
| Timestamps | `TIMESTAMP_NTZ` with UTC values default; consistent type per table |
| Clustering | Only for tables >1TB with confirmed query patterns; max 4 columns |
| Warehouses | Right-sized; auto-suspend 60–300s; isolated by workload |
| Multi-Cluster | For concurrency, not individual query speed |
| Data Loading | `COPY INTO` or Snowpipe; Parquet preferred; idempotent design |
| File Formats | Explicitly defined and reused; column name matching enabled |
| Queries | Project specific columns; filter early; enable pruning |
| Joins | Types declared with `RELY` constraints; compatible column types |
| Access Control | Role-based; future grants; managed access schemas |
| Masking | Policies on sensitive columns; role-based visibility |
| Resource Monitors | Required on all production warehouses; suspend triggers configured |
| Time Travel | Retention matched to recovery requirements; transient for staging |
| Streams | Append-only for insert-only sources; consume via tasks |
| Tasks | Conditional execution with `WHEN`; DAGs for dependencies |
| Dynamic Tables | `TARGET_LAG` declarative refresh; alternative to manual stream+task pipelines |
| Procedures | SQL Scripting for SQL-centric; Python for complex logic |
| UDFs | SQL for inline optimization; Python for complex transformations |
| External Tables | Query-in-place only; load frequently-queried data to native tables |
| Semi-Structured | `VARIANT` for flexibility; typed columns for frequent queries |
| Monitoring | Daily review of credit consumption; Query Profile for optimization |
| Deployment | Version-controlled DDL; CI/CD pipelines; clone-based testing |
| dbt | Incremental models; warehouse configuration in models; proper refs |
| Shakedown | Post-DDL canary against live account; pass / fail-blocking / fail-nonblocking / inconclusive; distinct `QUERY_TAG` for artifact recovery |
| Defense in Depth | Auto-suspend + RBAC + Time Travel/Fail-Safe + replication + monitors + DQ tests + ingestion alerts |
| Rule of Three | Pipeline + DQ test + freshness SLA MUST all agree before data is "ready" |

---
[Back to Overview](./OVERVIEW.md)
