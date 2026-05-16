# Required Practices

### Always Do

- Parameterize all queries with user-provided input.
- Define foreign keys for all relationships with explicit `ON DELETE` actions.
- Create indexes for foreign key columns on child tables.
- Include `created_at` and `updated_at` on all tables.
- Use transactions for multi-statement operations that must succeed or fail together.
- Analyze execution plans for queries running frequently or performing poorly.
- Version control all schema changes as migration scripts.
- Test migrations in non-production environments with realistic data.
- Monitor query performance and connection pool health.
- Apply principle of least privilege to all database accounts.
- Set query timeouts to prevent runaway operations.
- Document schema design decisions and denormalization rationale.
- Back up databases with **tested restore procedures**.
- Encrypt sensitive data at rest and in transit.
- Rotate credentials and encryption keys on schedule.
- Monitor for and respond to performance degradation.
- Maintain audit trails for data access and modifications.
- Run a §Shakedown after every triggering DDL, migration, reference data update, or permission change.

---
[Back to Overview](./OVERVIEW.md)
