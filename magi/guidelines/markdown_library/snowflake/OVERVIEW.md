# Snowflake Library

These guidelines define strict, cost-efficient, and scalable patterns for Snowflake data platform implementations, optimizing for:

- **Separation of Concerns** — Storage and compute are independent; scaling one does not affect the other; this architectural distinction drives every design decision.
- **Pay-Per-Second Economics** — Compute costs accrue by the second; every warehouse configuration, query pattern, and automation decision has direct cost implications.
- **Zero-Copy Architecture** — Data sharing, cloning, and time travel operate on metadata pointers, not physical copies; leverage this for cost-effective data distribution.
- **Declarative Simplicity** — Snowflake abstracts infrastructure management; fight the urge to over-engineer what the platform handles automatically.
- **Governance by Default** — Access control, data lineage, and audit logging are first-class citizens; build security into the architecture, not as an afterthought.

## Critical Mandates (Read First)

- **Warehouse Discipline Is Cost Discipline** — Auto-suspend, right-sizing, and workload isolation are requirements; every warehouse must justify its existence, size, and runtime configuration.
- **Metadata Is Your Competitive Advantage** — Design schemas and queries to maximize metadata utilization; the optimizer is only as good as the information you give it.
- **Auto-Suspend Required** — `AUTO_SUSPEND = 0` is forbidden; idle warehouses burn credits continuously.
- **Shakedown After Every DDL Apply** — Run a §20 shakedown after every triggering change against the live account.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [Account and Organization Architecture](./ACCOUNT_ARCHITECTURE.md)
3. [Database and Schema Design](./DATABASE_SCHEMA_DESIGN.md)
4. [Table Design and Data Types](./TABLE_DESIGN.md)
5. [Clustering and Micro-Partitioning](./CLUSTERING.md)
6. [Virtual Warehouse Configuration](./WAREHOUSE_CONFIGURATION.md)
7. [Data Loading Strategies](./DATA_LOADING.md)
8. [Query Optimization](./QUERY_OPTIMIZATION.md)
9. [Access Control and Security](./ACCESS_CONTROL.md)
10. [Resource Monitors and Cost Management](./RESOURCE_MONITORS.md)
11. [Time Travel and Fail-Safe](./TIME_TRAVEL.md)
12. [Data Sharing and Marketplace](./DATA_SHARING.md)
13. [Streams and Tasks](./STREAMS_TASKS.md)
14. [Dynamic Tables](./DYNAMIC_TABLES.md)
15. [Stored Procedures and User-Defined Functions](./STORED_PROCEDURES.md)
16. [External Tables and Data Lake Integration](./EXTERNAL_TABLES.md)
17. [Semi-Structured Data Handling](./SEMI_STRUCTURED.md)
18. [Monitoring and Observability](./MONITORING.md)
19. [Development and Deployment Patterns](./DEVELOPMENT_DEPLOYMENT.md)
20. [Shakedown — Post-DDL Integration Validation](./SHAKEDOWN.md)
21. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
22. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
23. [Required Practices](./REQUIRED_PRACTICES.md)
24. [Style Summary](./STYLE_SUMMARY.md)
