# Operational Safety for Destructive Operations

### Guardrails for DELETE/UPDATE

Production `DELETE` or broad `UPDATE` must follow a two-step pattern:

1. Run a `SELECT` with the same predicate to verify row count and sample results.
2. Run the destructive statement with the exact same predicate.

For large deletes/updates:

- Use batches with deterministic ordering and commit between batches.
- Monitor lock waits and log growth during execution.
- **Never run `DELETE`/`UPDATE` without a `WHERE` clause in production.**

```sql
-- Safe batch delete pattern
DECLARE @batch_size INT = 10000;
DECLARE @deleted INT = 1;

WHILE @deleted > 0
BEGIN
    DELETE TOP (@batch_size) FROM log_entry
    WHERE created_at < DATEADD(YEAR, -1, GETDATE());

    SET @deleted = @@ROWCOUNT;

    -- Optional: Small delay to reduce contention
    WAITFOR DELAY '00:00:01';
END
```

### Safe Rollouts for Data Fixes

- Prefer "write new, then switch reads" patterns (expand-contract) for corrective data changes.
- Maintain an audit trail for any corrective operation affecting many rows: who ran it, when, why, what scope, and how it was validated.

### Break-Glass Access

- Maintain a documented break-glass process: separate credentials, time-bounded access, mandatory audit logging, post-incident review and credential rotation.

---
[Back to Overview](./OVERVIEW.md)
