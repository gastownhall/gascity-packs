# Core Principles

These guidelines define strict, performant, and maintainable patterns for all SQL code and relational database design, optimizing for:

- **Query Determinism** — Every query produces predictable results regardless of execution plan variations or data distribution changes.
- **Schema Integrity** — Constraints enforce business rules at the database level; the application layer is not trusted as the sole validator.
- **Performance by Design** — Indexing strategy, query structure, and schema normalization decisions made upfront, not retrofitted after production fires.
- **Explicit Intent** — No implicit conversions, no ambiguous column references, no reliance on database-specific default behaviors.
- **Auditability** — Every schema change tracked, every destructive operation logged, every permission grant justified.

### Primary Rule: The Database Is the Last Line of Defense

Application code changes frequently. Developers make mistakes. Network requests get replayed. The database schema and its constraints must enforce invariants that protect data integrity regardless of what the application layer does. **If a constraint can be expressed in DDL, it belongs in DDL.**

### Secondary Rule: Optimize for Read Patterns

Most systems read far more than they write. Schema design, indexing, and denormalization decisions should prioritize the query patterns that execute thousands of times per minute over the insert that happens once. Measure before optimizing, but design with read-heavy workloads as the default assumption.

### Tertiary Rule: Measure Before Acting

Database optimization without measurement is superstition. Execution plans, wait statistics, I/O metrics, and query timing data must inform every performance decision. Intuition about what is slow is frequently wrong; the query planner often knows better than you do.

- `EXPLAIN ANALYZE` for query tuning.
- Benchmark before and after indexing changes.
- Monitor production query patterns.

### Dialect Awareness

These guidelines apply broadly to ANSI SQL with notes for PostgreSQL, SQL Server, MySQL, and SQLite where behaviors diverge. When writing cross-platform SQL, prefer ANSI-compliant syntax. When targeting a specific engine, leverage its strengths but document the dependency.

---
[Back to Overview](./OVERVIEW.md)
