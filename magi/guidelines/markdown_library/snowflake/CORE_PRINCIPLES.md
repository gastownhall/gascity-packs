# Core Principles

These guidelines define strict, cost-efficient, and scalable patterns for Snowflake data platform implementations, optimizing for:

- **Separation of Concerns** — Storage and compute are independent; scaling one does not affect the other; this architectural distinction drives every design decision.
- **Pay-Per-Second Economics** — Compute costs accrue by the second; every warehouse configuration, query pattern, and automation decision has direct cost implications.
- **Zero-Copy Architecture** — Data sharing, cloning, and time travel operate on metadata pointers, not physical copies; leverage this for cost-effective data distribution.
- **Declarative Simplicity** — Snowflake abstracts infrastructure management; fight the urge to over-engineer what the platform handles automatically.
- **Governance by Default** — Access control, data lineage, and audit logging are first-class citizens; build security into the architecture, not as an afterthought.

### Primary Rule: Warehouse Discipline Is Cost Discipline

Snowflake's pricing model charges for compute time. **A warehouse running unnecessarily for one hour costs the same as processing one hour of legitimate workload.** Auto-suspend, right-sizing, and workload isolation are not optimizations — they are requirements. Every warehouse must justify its existence, its size, and its runtime configuration. Unmonitored warehouses become budget leaks that compound silently until the invoice arrives.

```sql
-- CORRECT: auto-suspend always configured
CREATE WAREHOUSE analytics_wh
    WAREHOUSE_SIZE = 'MEDIUM'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE;

-- WRONG: NEVER DO THIS
CREATE WAREHOUSE always_on_wh
    WAREHOUSE_SIZE = 'X-LARGE'
    AUTO_SUSPEND = 0;
```

### Secondary Rule: Metadata Is Your Competitive Advantage

Snowflake's query optimizer relies on metadata statistics, micro-partition pruning, and clustering information to execute queries efficiently. Queries that defeat pruning — through functions on partition columns, non-deterministic predicates, or poor clustering choices — bypass the optimization layer and scan unnecessary data. Design schemas and queries to maximize metadata utilization. **The optimizer is only as good as the information you give it.**

### Architectural Foundations

| Layer | Billing | Description |
|:------|:--------|:------------|
| Storage | Per-TB-month | Compressed, columnar storage in cloud object storage (S3, Azure Blob, GCS); immutable micro-partitions of 50–500MB compressed; no indexes — pruning replaces indexing |
| Compute | Per-second | Virtual warehouses providing isolated compute clusters; T-shirt sizing X-Small to 6X-Large; spin up in seconds; auto-suspend after configurable idle |
| Cloud Services | 10% threshold | Coordinates metadata, query parsing, optimization, access control, infrastructure; charges only when consumption exceeds 10% of daily compute credits |

### Edition Considerations

| Edition | Key features |
|:--------|:-------------|
| Standard | Core functionality; **1-day Time Travel maximum** |
| Enterprise | 90-day Time Travel, multi-cluster warehouses, materialized views, column-level security, row access policies |
| Business Critical | Enhanced security (HIPAA, PCI-DSS), failover/failback, AWS PrivateLink, Azure Private Link |
| VPS | Dedicated infrastructure; maximum isolation |

Choose the edition that matches compliance requirements and feature needs. **Don't pay for Enterprise features you won't use; don't operate Business Critical workloads on Standard edition.**

---
[Back to Overview](./OVERVIEW.md)
