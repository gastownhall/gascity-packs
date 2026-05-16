# Shakedown — Post-Schema-Change Validation

### Definition

A SQL shakedown is a **mandatory integration-validation pass executed against the real target database** after any DDL, migration, reference data update, or permission change. It confirms the schema, constraints, views, stored procedures, grants, and plan budgets behave correctly as an integrated whole against known-good inputs.

| Phase | Question |
|:------|:---------|
| Preflight | Database reachable, connection string resolves, migration tool installed |
| **Shakedown** | **Freshly migrated schema accepts a known-good transaction round-trip end to end** |
| Testing | Functional/performance tests at scale |

**Shakedown is never replaced by unit tests against mocks or in-memory databases.**

### Mandatory Triggers

- DDL of any kind: `CREATE`, `ALTER`, `DROP` on tables, columns, indexes, sequences, types.
- Migration tool run (Flyway, Liquibase, Alembic, sqitch, custom).
- Reference data reload or seed data refresh.
- View, materialized view, stored procedure, function, or trigger create/replace.
- Grant, revoke, role, or row-level-security policy change.
- Database engine upgrade, extension install, or collation change.
- Replication topology change or failover rehearsal.
- Restore from backup into a target environment.

### Non-Triggers

- Routine OLTP traffic against an unchanged schema.
- Application-level config changes that do not alter connection strings.
- Query tuning that does not ship new indexes or new SQL to production.
- Statistics-only refreshes (`ANALYZE`, `UPDATE STATISTICS`).

### Validation Categories

Every category is exercised against known-good canary rows in a dedicated shakedown schema or sandbox database.

1. **Migration state** — the migration tool reports zero pending migrations and the current version matches the expected head.
2. **Reference query row counts** — a curated set of reference `SELECT` queries returns row counts within declared expected bounds (exact, min, or min/max).
3. **Foreign-key enforcement** — a deliberate `INSERT` that violates a foreign key is rejected with the expected SQLSTATE (`23503` or engine equivalent); a valid parent-child `INSERT` succeeds.
4. **Check-constraint enforcement** — a deliberate `INSERT` or `UPDATE` that violates a `CHECK` constraint is rejected with `23514` or engine equivalent.
5. **Unique-index enforcement** — a deliberate duplicate `INSERT` against a `UNIQUE` index is rejected with `23505` or engine equivalent.
6. **View shape** — every view and materialized view referenced by the application is queried once and the column list, types, and row count bounds are validated; materialized views are refreshed and the refresh duration is captured.
7. **Routine compilation** — every stored procedure, function, and trigger is inspected in system catalogs as `VALID` and invoked once with canary parameters against the new schema.
8. **Permissions / grants** — the application service account executes the canary round-trip; a forbidden object access is confirmed to return an insufficient-privilege error.
9. **Plan-budget baseline** — `EXPLAIN` (or equivalent) output is captured for every critical query and diffed against the previous shakedown baseline; regressions are logged as non-blocking observations, never as hard failures during shakedown.

### Execution Principles

- **Conservative execution** — one canary row per table, one canary transaction per stored procedure; **never production data**, never adversarial inputs.
- **Progressive stress** — start with the simplest INSERT/SELECT/DELETE round-trip, then add the view query, then the stored procedure, then the trigger path; stop at the first failure and diagnose.
- **Controlled environment** — a dedicated shakedown database or schema that mirrors production DDL, extensions, collations, and grants.
- **Observable execution** — every statement captures execution plan, row counts, SQLSTATE on error, and wall-clock duration.
- **Known-good inputs** — a fixed seed dataset with declared expected row counts, aggregates, and join cardinalities.
- **No optimization during shakedown** — a plan regression or missing index is logged as a non-blocking finding; index tuning is a separate change that itself triggers a new shakedown.

### Execution Order

1. Confirm preflight passes — database reachable, credentials resolve, migration tool version matches, extensions present.
2. Initialize the canary scope — shakedown schema cleared of previous canary rows, lease transaction opened, expected-row-count table loaded.
3. Execute the simplest end-to-end path — `INSERT` canary row, `SELECT` it back, `UPDATE` it, `DELETE` it; assert each affected-row count.
4. Verify view shape — query every application-referenced view, assert column list, types, declared row-count bounds.
5. Verify constraint enforcement — execute the deliberate FK, CHECK, and UNIQUE violation attempts and assert each is rejected with the expected SQLSTATE.
6. Verify routine compilation and execution — call every stored procedure and function once with canary parameters.
7. Verify permissions — repeat the canary round-trip as the application service account; attempt one forbidden operation and assert denial.
8. Capture `EXPLAIN` plans for critical queries and diff against the previous baseline.
9. Check for orphans — canary rows removed, temp tables dropped, open transactions closed, replication lag within bounds.
10. Classify the result per validation category.

### Result Classification

| Outcome | Trigger |
|:--------|:--------|
| `pass` | Every category completes with the expected SQLSTATE, row counts, and view shape |
| `fail-blocking` | A constraint fails to enforce, a stored procedure errors under the new schema, a grant is missing, a view returns the wrong shape, or a migration reports out-of-order state |
| `fail-nonblocking` | A plan regression relative to the previous baseline that does not change correctness; logged for a subsequent tuning change |
| `inconclusive` | A connection timeout, replication lag spike, or environment drift prevented a category from completing — re-run the specific category before declaring shakedown failed |

### Required Artifacts

- Execution log — timestamped SQL log with statement text, SQLSTATE, affected row count, duration per statement.
- Result summary — pass/fail classification per validation category.
- Issue list — every non-blocking anomaly with reproduction context and the originating migration id.
- Environment snapshot — engine version, extension versions, collation, migration head, grant list, plan baseline at the time of shakedown.

### Anti-Patterns

- Skipping shakedown after a "small" `ALTER` because the change "only adds a column".
- Running shakedown against an in-memory or SQLite stand-in when production is PostgreSQL, MySQL, SQL Server, or Oracle.
- Treating shakedown as a full regression suite with hundreds of assertions.
- Fixing plan regressions mid-shakedown instead of logging them and re-running a clean shakedown after the fix.
- Running shakedown without capturing SQLSTATE, affected row counts, or `EXPLAIN` output.
- Omitting permission validation because "the DBA already granted it".

### Reference Canary SQL

```sql
-- Shakedown: post-migration round-trip against a dedicated canary schema
BEGIN;

-- 1. Migration state
SELECT version, checksum, success
FROM flyway_schema_history
ORDER BY installed_rank DESC
LIMIT 1;  -- expected: version = head, success = true

-- 2. Reference row count
SELECT COUNT(*) AS user_count FROM shakedown.user_canary;
-- expected: 3

-- 3. Canary round-trip
INSERT INTO shakedown.user_canary (id, email, status)
VALUES (1001, 'canary@example.com', 'active');
SELECT id, email, status FROM shakedown.user_canary WHERE id = 1001;
UPDATE shakedown.user_canary SET status = 'inactive' WHERE id = 1001;
DELETE FROM shakedown.user_canary WHERE id = 1001;

-- 4. Foreign key enforcement (expected: SQLSTATE 23503)
SAVEPOINT fk_check;
INSERT INTO shakedown.order_canary (id, user_id, total)
VALUES (9999, 999999, 10.00);
ROLLBACK TO SAVEPOINT fk_check;

-- 5. Unique index enforcement (expected: SQLSTATE 23505)
SAVEPOINT unique_check;
INSERT INTO shakedown.user_canary (id, email, status)
VALUES (2002, 'existing@example.com', 'active');
INSERT INTO shakedown.user_canary (id, email, status)
VALUES (2003, 'existing@example.com', 'active');
ROLLBACK TO SAVEPOINT unique_check;

-- 6. View shape
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'shakedown' AND table_name = 'active_user_view'
ORDER BY ordinal_position;

-- 7. Routine execution
SELECT shakedown.fn_canary_round_trip(1001);

-- 8. Plan baseline
EXPLAIN (FORMAT JSON) SELECT * FROM shakedown.order_canary WHERE user_id = 1001;

ROLLBACK;  -- shakedown never persists canary state
```

---
[Back to Overview](./OVERVIEW.md)
