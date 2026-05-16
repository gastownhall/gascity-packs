# Testing and Quality Gates

### Schema and Migration Testing

- Validate migrations against:
  - Empty database.
  - Production-like data volume.
  - Rollback path (down) if supported by your migration tooling.
- Enforce **no drift**: schema produced by applying migrations from scratch must match the schema in a migrated environment.
- Gate migrations on successful apply, successful verification queries, safe rollback (or explicitly documented non-rollbackable migrations).

### Query Performance Testing

For critical queries:

- Capture baseline plans and p95/p99 timings.
- Re-test on schema/index changes.
- Use realistic parameters and data distributions to avoid misleading plans.

### Data Integrity Testing

- Add automated checks for invariants that are hard to encode as constraints: cross-table consistency assertions, orphan detection, duplicate detection for business keys.
- Run integrity checks regularly in non-production and periodically in production where safe.

### Database Unit Testing (pgTAP example)

```sql
-- pgTAP example for PostgreSQL
BEGIN;
SELECT plan(3);

-- Test constraint
SELECT throws_ok(
    'INSERT INTO user (email) VALUES (NULL)',
    '23502',
    'null value in column "email" violates not-null constraint'
);

-- Test function
SELECT is(
    process_order(NULL, '[]'::jsonb, 'credit_card'),
    ROW(NULL::BIGINT, 'error'::VARCHAR, 'User ID required'::TEXT)::record,
    'Should return error for null user_id'
);

-- Test trigger
INSERT INTO user (email) VALUES ('test@example.com');
SELECT is(
    (SELECT updated_at FROM user WHERE email = 'test@example.com'),
    CURRENT_TIMESTAMP,
    'Trigger should set updated_at'
);

SELECT * FROM finish();
ROLLBACK;
```

### Release Discipline

Any change that affects indexes, constraints, column types, or large tables must have a documented rollout plan and measurable success criteria. Post-deploy verification is required:

- Confirm key query latencies did not regress.
- Confirm error rates and deadlocks did not increase.
- Confirm replication lag (if applicable) remained within tolerance.

---
[Back to Overview](./OVERVIEW.md)
