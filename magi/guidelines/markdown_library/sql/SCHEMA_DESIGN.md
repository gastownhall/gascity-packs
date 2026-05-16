# Schema Design

### Normalization Baseline

- Start at Third Normal Form (3NF) for transactional systems.
- Denormalize deliberately and document the reason: read performance, reporting requirements, eliminating expensive joins.
- Every denormalization creates a consistency obligation; ensure update mechanisms maintain integrity.
- Consider Boyce-Codd Normal Form (BCNF) when functional dependencies are complex.
- Fourth Normal Form (4NF) eliminates multi-valued dependencies; apply when independent multi-valued facts exist.

### When to Denormalize

Denormalization is a performance trade-off, not a simplification. Accept it only when:

- Joins are measured to be the bottleneck, not suspected.
- The duplicated data changes infrequently relative to read frequency.
- Update mechanisms (triggers, application code, CDC) reliably maintain consistency.
- The denormalized structure is documented with the consistency strategy.

Common legitimate denormalizations:

- Caching aggregate values (order totals, inventory counts) with trigger-maintained updates.
- Storing lookup values (status names, category names) for reporting tables.
- Flattening hierarchical data for read-heavy reporting.
- Duplicating frequently joined columns to avoid expensive cross-table lookups.

### Primary Keys

- Prefer surrogate keys (`id` as auto-incrementing integer or UUID) for most tables.
- Use natural keys only when they are truly immutable, unique, and meaningful: ISO country codes, currency codes, well-defined external identifiers.
- Composite primary keys are acceptable for junction tables and when the combination is the natural identifier.
- **UUID considerations**: Use UUIDv7 (time-ordered) for clustered indexes to avoid page splits; UUIDv4 fragments B-trees.
- **IDENTITY/SERIAL sizing**: Use `BIGINT` for high-volume tables where int overflow is conceivable over the table lifetime.
- Never reuse primary key values; deleted row identifiers remain permanently retired.

### Foreign Keys

Every foreign key relationship requires an explicit `FOREIGN KEY` constraint. Define `ON DELETE` and `ON UPDATE` actions explicitly; **never rely on database defaults**.

| Pattern | Use |
|:--------|:----|
| `ON DELETE CASCADE` | Child records meaningless without parent (order items when order deleted) |
| `ON DELETE RESTRICT` | Prevent deletion while references exist (users with orders) |
| `ON DELETE SET NULL` | Preserve child but remove association (optional relationships) |
| `ON DELETE NO ACTION` | Similar to RESTRICT but allows deferred constraint checking |

- Avoid circular foreign key dependencies; they complicate inserts and deletes.
- For self-referential hierarchies, `ON DELETE SET NULL` or `ON DELETE RESTRICT` are typical; CASCADE creates recursive delete chains.
- **Always index foreign key columns on the child table**; unindexed FKs cause table scans during parent modifications.

### Soft Deletes

- Use `deleted_at` timestamp rather than `is_deleted` boolean; the timestamp provides audit value.
- Create partial indexes excluding soft-deleted rows for queries that filter them.
- Consider separate archive tables for high-volume soft-delete scenarios to keep primary table performant.
- Application and query layers must consistently filter deleted records; create views to encapsulate this.
- Define retention policy: soft-deleted records should be hard-deleted or archived after a defined period.
- Be explicit about soft-delete semantics for foreign key relationships: cascading soft deletes require application logic.

### Audit Columns

Standard audit columns for most tables:

- `created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP` with trigger to update on modification
- `created_by` and `updated_by` referencing the actor when applicable
- For compliance-heavy systems: `version` column for optimistic locking, `change_reason` for regulated changes

```sql
-- PostgreSQL trigger for updated_at
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_user_updated_at
    BEFORE UPDATE ON app_user
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();
```

```sql
-- SQL Server trigger for updated_at
CREATE TRIGGER tr_user_updated_at
ON app_user
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE app_user
    SET updated_at = GETUTCDATE()
    FROM app_user u
    INNER JOIN inserted i ON i.id = u.id;
END;
```

### Temporal Tables (System-Versioned)

For compliance, auditing, or point-in-time queries, consider system-versioned temporal tables:

- SQL Server: `CREATE TABLE ... WITH (SYSTEM_VERSIONING = ON)`
- PostgreSQL: Use `temporal_tables` extension or manual history tables

Temporal table requirements:

- Period columns (`valid_from`, `valid_until`) must be `NOT NULL` `datetime2`/`timestamp`.
- History table stores all previous row versions automatically.
- Queries can specify `FOR SYSTEM_TIME AS OF` for point-in-time retrieval.
- Retention policies prevent unbounded history growth.

### Change Data Capture (CDC)

For event-driven architectures or data warehouse synchronization:

- Enable CDC on tables requiring change tracking.
- Monitor CDC cleanup latency; blocked cleanup causes log growth.
- Design consumers to handle out-of-order delivery and duplicates.
- Consider Debezium or similar tools for cross-platform CDC needs.

### Partitioning

- Partition tables exceeding 10 million rows or where queries consistently filter on a partitionable dimension.
- Time-based partitioning (daily, monthly) for event logs, transactions, audit trails.
- Range partitioning for sequential identifiers or dates.
- List partitioning for categorical data with known, stable values.
- Avoid over-partitioning; each partition adds planning overhead.

Partition design considerations:

- Partition elimination must occur for common queries; verify with execution plans.
- Partition switching enables bulk loads and archival without blocking.
- Local indexes exist per partition; global indexes span all partitions (SQL Server: partitioned indexes).
- PostgreSQL 12+ native partitioning is preferred over inheritance-based partitioning.
- Partition maintenance (creation, dropping) should be automated.

### Table Compression

| Type | Trade-offs |
|:-----|:-----------|
| Row compression | Reduces storage for fixed-length types; minimal CPU overhead |
| Page compression | Adds dictionary and prefix compression; more CPU but better ratios |
| Columnstore compression | Best for analytics workloads with bulk reads |

Evaluate compression on representative data; not all data compresses equally. Monitor CPU impact on write-heavy tables.

### Filegroup and Tablespace Strategy

Separate database objects by I/O characteristics:

- Place transaction log on dedicated fast storage.
- Separate high-I/O tables (audit logs, events) from primary data.
- Consider read-only filegroups for historical data.
- TempDB requires dedicated fast storage; multiple data files reduce contention.

---
[Back to Overview](./OVERVIEW.md)
