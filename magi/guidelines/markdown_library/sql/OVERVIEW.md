# SQL and Relational Database Library

These guidelines define strict, performant, and maintainable patterns for all SQL code and relational database design, optimizing for:

- **Query Determinism** — Every query produces predictable results regardless of execution plan variations or data distribution changes.
- **Schema Integrity** — Constraints enforce business rules at the database level; the application layer is not trusted as the sole validator.
- **Performance by Design** — Indexing strategy, query structure, and schema normalization decisions made upfront, not retrofitted after production fires.
- **Explicit Intent** — No implicit conversions, no ambiguous column references, no reliance on database-specific default behaviors.
- **Auditability** — Every schema change tracked, every destructive operation logged, every permission grant justified.

## Critical Mandates (Read First)

- **The Database Is the Last Line of Defense** — Application code changes frequently, developers make mistakes, network requests get replayed; the database schema and its constraints must enforce invariants regardless of what the application layer does. **If a constraint can be expressed in DDL, it belongs in DDL.**
- **Optimize for Read Patterns** — Most systems read far more than they write; schema design, indexing, and denormalization decisions should prioritize the query patterns that execute thousands of times per minute over the insert that happens once.
- **Measure Before Acting** — Database optimization without measurement is superstition; execution plans, wait statistics, I/O metrics, and query timing data must inform every performance decision.
- **Dialect Awareness** — These guidelines apply broadly to ANSI SQL with notes for PostgreSQL, SQL Server, MySQL, and SQLite where behaviors diverge; prefer ANSI-compliant syntax when targeting cross-platform.

## Table of Contents

### Foundation

1. [Core Principles](./CORE_PRINCIPLES.md)

### Part I: Design

2. [Naming Conventions](./NAMING_CONVENTIONS.md)
3. [Schema Design](./SCHEMA_DESIGN.md)
4. [Data Types and Constraints](./DATA_TYPES.md)
5. [Indexing Strategy](./INDEXING.md)

### Part II: Implementation

6. [Query Formatting and Structure](./QUERY_FORMATTING.md)
7. [Joins and Relationships](./JOINS.md)
8. [Stored Procedures and Functions](./STORED_PROCEDURES.md)
9. [Views and Common Table Expressions](./VIEWS_CTES.md)
10. [Query Optimization](./QUERY_OPTIMIZATION.md)

### Part III: Execution

11. [Transactions and Concurrency](./TRANSACTIONS.md)
12. [NOLOCK and Read Uncommitted](./NOLOCK.md)
13. [Connection and Resource Management](./CONNECTION_MANAGEMENT.md)
14. [Performance Tuning](./PERFORMANCE_TUNING.md)

### Part IV: Operations

15. [Migration Management](./MIGRATION_MANAGEMENT.md)
16. [Maintenance, Backups, and Recovery](./MAINTENANCE_BACKUPS.md)
17. [Security Practices](./SECURITY.md)
18. [Monitoring and Diagnostics](./MONITORING.md)
19. [Operational Safety for Destructive Operations](./DESTRUCTIVE_OPERATIONS.md)
20. [Testing and Quality Gates](./TESTING.md)
21. [Temporary Staging and zlink Tables](./STAGING_ZLINK.md)
22. [Shakedown — Post-Schema-Change Validation](./SHAKEDOWN.md)
23. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
24. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
25. [Required Practices](./REQUIRED_PRACTICES.md)
26. [Style Summary](./STYLE_SUMMARY.md)
