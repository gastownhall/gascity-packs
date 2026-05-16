# Migration Management

### Migration Principles

- Every schema change captured in a versioned migration script.
- Migrations are immutable once applied to production; create new migrations for fixes.
- Migrations must be idempotent where possible; use `IF NOT EXISTS`, `IF EXISTS` guards.
- Test migrations in non-production environments with production-like data volumes.

### Migration File Naming

```text
20250619_001_create_user_table.sql
20250619_002_add_email_index.sql
20250620_001_alter_order_add_status.sql
```

### Forward and Rollback Scripts

- Every migration includes an `up` (apply) and `down` (rollback) section.
- Rollback scripts must fully reverse the migration.
- Test rollback scripts; untested rollbacks fail when you need them most.

### Breaking vs Non-Breaking Changes

| Non-breaking (deploy anytime) | Breaking (requires coordination) |
|:------------------------------|:---------------------------------|
| Adding nullable columns with defaults | Removing or renaming columns |
| Adding new tables | Changing column types |
| Adding new indexes (be aware of lock duration) | Adding `NOT NULL` without default |
| Adding new constraints that existing data satisfies | Removing tables or indexes |

### Deployment Strategy

- Apply non-breaking changes first; deploy application code; apply breaking changes that remove deprecated elements.
- Use **expand-contract pattern**: add new structure, migrate data, update application, remove old structure.
- Large data migrations run in batches during low-traffic windows.
- Monitor for blocking and deadlocks during migration execution.

### Data Migrations

- Separate schema migrations from data migrations in tooling and execution.
- Data migrations should be resumable; track progress to restart from failure point.
- Log data migration metrics: rows processed, time elapsed, errors encountered.

### Migration Safety Enhancements

- Prefer online/non-blocking index builds where supported:
  - SQL Server: consider `ONLINE = ON` where edition and index type allow it.
  - PostgreSQL: use `CREATE INDEX CONCURRENTLY` for large tables (cannot run inside a transaction block).
- Add constraints in a validated, low-risk manner when supported:
  - PostgreSQL: `NOT VALID` constraints followed by `VALIDATE CONSTRAINT` to avoid long blocking.
  - SQL Server: `WITH NOCHECK` followed by validation (though this leaves constraint untrusted; prefer proper validation).
- Always set timeouts for migration sessions when the engine supports them.
- Avoid coupling schema changes and large backfills in the same deploy step unless the migration tooling and rollout plan explicitly supports long-running operations.

```sql
-- PostgreSQL: Safe index creation
CREATE INDEX CONCURRENTLY ix_large_table_column ON large_table (column);

-- PostgreSQL: Safe constraint addition
ALTER TABLE large_table ADD CONSTRAINT ck_large_table_positive
    CHECK (amount > 0) NOT VALID;
-- Later, in a separate migration:
ALTER TABLE large_table VALIDATE CONSTRAINT ck_large_table_positive;
```

### Reference Migration

```sql
-- File: V1.2.0__add_user_status.sql
BEGIN;
-- Add column as nullable first
ALTER TABLE user ADD COLUMN status VARCHAR(20);
-- Backfill in batches (outside transaction for large tables)
UPDATE user SET status = 'active' WHERE status IS NULL;
-- Add constraint after backfill
ALTER TABLE user ALTER COLUMN status SET NOT NULL;
ALTER TABLE user ALTER COLUMN status SET DEFAULT 'active';
-- Add index
CREATE INDEX CONCURRENTLY ix_user_status ON user(status);
-- Add check constraint
ALTER TABLE user ADD CONSTRAINT ck_user_status
    CHECK (status IN ('active', 'inactive', 'suspended'));
COMMIT;

-- Rollback script
-- File: V1.2.0__add_user_status.rollback.sql
BEGIN;
ALTER TABLE user DROP CONSTRAINT IF EXISTS ck_user_status;
DROP INDEX IF EXISTS ix_user_status;
ALTER TABLE user DROP COLUMN IF EXISTS status;
COMMIT;
```

### Zero-Downtime Migrations

```sql
-- Pattern: Rename column with zero downtime

-- Step 1: Add new column
ALTER TABLE user ADD COLUMN email_address VARCHAR(320);

-- Step 2: Dual write (application writes to both)
UPDATE user SET email_address = email WHERE email_address IS NULL;

-- Step 3: Add trigger for consistency
CREATE OR REPLACE FUNCTION sync_email_columns()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.email IS DISTINCT FROM OLD.email THEN
        NEW.email_address := NEW.email;
    ELSIF NEW.email_address IS DISTINCT FROM OLD.email_address THEN
        NEW.email := NEW.email_address;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_sync_email
BEFORE UPDATE ON user
FOR EACH ROW EXECUTE FUNCTION sync_email_columns();

-- Step 4: Application reads from new column
-- Step 5: Stop writing to old column
-- Step 6: Drop trigger and old column
DROP TRIGGER IF EXISTS tr_sync_email ON user;
DROP FUNCTION IF EXISTS sync_email_columns();
ALTER TABLE user DROP COLUMN email;
```

---
[Back to Overview](./OVERVIEW.md)
