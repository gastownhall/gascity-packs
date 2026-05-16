# Azure Cosmos DB Guidelines Library

This directory contains an expanded, modularized version of the Azure Cosmos DB Guidelines. Apply universally to all Azure Cosmos DB implementations across the organization.

## Critical Mandates (Read First)
- **Model for Your Access Patterns** — Cosmos DB is not a relational database; data model serves access patterns, not entity relationships.
- **Partition Key Is Destiny** — the most consequential architectural choice; cannot be fixed without data migration.
- **Denormalize by Default** — duplicate data to eliminate multi-document reads.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md) — Partition-aware design, RU economy, denormalization, consistency intentionality, horizontal scale; API selection.
2. [Data Modeling Strategy](./DATA_MODELING.md) — Denormalization, embedding vs reference, document structure, size, polymorphic containers, references, arrays.
3. [Partition Key Design](./PARTITION_KEY.md) — Fundamentals, selection criteria, patterns, anti-patterns, immutability, logical partition limits.
4. [Container and Database Architecture](./CONTAINER_ARCHITECTURE.md) — Throughput, design, naming, settings, unique key constraints.
5. [Indexing Configuration](./INDEXING.md) — Default, selective, exclusion, composite, spatial, transformation.
6. [Query Optimization](./QUERY_OPTIMIZATION.md) — Single-partition, projection, pagination, filtering, aggregations, JOIN, subqueries, plan analysis.
7. [Throughput Management](./THROUGHPUT.md) — Models, selection, RU budgeting, rate limiting.
8. [Consistency Levels](./CONSISTENCY_LEVELS.md) — Spectrum, default, selection, multi-region.
9. [SDK Usage Patterns](./SDK_USAGE.md) — Client init, connection mode, point ops, upsert, ETags, bulk, transactional batch, streaming, integrated cache.
10. [Change Feed Processing](./CHANGE_FEED.md) — Fundamentals, use cases, processor, handler, lease container, Functions integration.
11. [Transactions and Stored Procedures](./TRANSACTIONS_PROCS.md) — Boundaries, batch, stored procedures, triggers, UDFs.
12. [Time-to-Live and Data Lifecycle](./TTL_LIFECYCLE.md) — Configuration, use cases, mechanics, archival.
13. [Multi-Region Configuration](./MULTI_REGION.md) — Topologies, read region selection, failover, conflict resolution, consistency.
14. [Security Practices](./SECURITY.md) — Authentication, RBAC, network, encryption, key rotation.
15. [Monitoring and Diagnostics](./MONITORING.md) — Metrics, Azure Monitor, alerting, SDK diagnostics.
16. [Cost Optimization](./COST_OPTIMIZATION.md) — RU reduction, throughput, storage, reserved capacity, decision tree.
17. [Post-Change Shakedown](./SHAKEDOWN.md) — Definition, triggers, validation surfaces, execution, classification, artifacts, anti-patterns.
18. [Defense in Depth](./DEFENSE_IN_DEPTH.md) — Independent layers, Rule of Three.
19. [Prohibited Practices](./PROHIBITED_PRACTICES.md) — Never Do / Always Do lists.
20. [Style Summary](./STYLE_SUMMARY.md) — Quick-reference table for required styles.
