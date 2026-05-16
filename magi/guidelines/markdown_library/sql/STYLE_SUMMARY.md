# Style Summary

| Element | Required Style |
|:--------|:---------------|
| Line Length | Maximum 200 characters |
| Keywords | UPPERCASE: `SELECT`, `FROM`, `WHERE`, `JOIN` |
| Identifiers | `snake_case` for tables, columns, constraints |
| Table Names | Singular nouns: `user`, `order_item`, not `users`, `order_items` |
| Primary Keys | `id` for surrogate; `{table}_id` as foreign key reference |
| Boolean Columns | Prefix with `is_`, `has_`, `can_`: `is_active`, `has_subscription` |
| Timestamps | Suffix `_at`: `created_at`, `updated_at`, `deleted_at` |
| Indexes | `ix_{table}_{columns}` |
| Constraints | `uq_`, `ck_`, `fk_`, `df_` prefixes |
| Joins | Explicit `JOIN ... ON` syntax; never comma-separated tables |
| Table Aliases | Short, meaningful: `u` for `user`, `oi` for `order_item` |
| Column Qualification | Always qualify columns in multi-table queries |
| Transactions | Explicit boundaries; short duration; proper isolation level |
| Parameterization | All user input parameterized; no concatenation |
| Migrations | Versioned scripts with up/down; immutable once deployed |
| Stored Procedures | Set-based logic; explicit error handling; documented |
| Views | Named with `v_` prefix; documented filter conditions |
| Data Types | Smallest appropriate type; explicit precision for decimals |
| Constraints | `NOT NULL` default; check constraints for domain rules |
| Indexes | Based on query patterns; composite indexes ordered by selectivity |
| NOLOCK | Documented justification; never for transactional reads |
| Temp/zlink Tables | Time-bounded; isolated; indexed; auditable; always cleaned up |
| Backups/Recovery | Restore-tested; defined RPO/RTO; monitored backup success |
| Security | Least privilege; encryption in transit and at rest; audit logging |
| Window Functions | Use for ranking and running calculations; avoid subqueries that scan multiple times |
| Optimistic Locking | Version column + conditional UPDATE for low-contention multi-step updates |
| Audit Logging | Generic trigger writing to `audit_log` table with old/new JSONB values |
| Shakedown | Post-DDL canary round-trip; pass / fail-blocking / fail-nonblocking / inconclusive; SQLSTATE-asserted |
| Defense in Depth | EXPLAIN review + SQL lint + versioned migrations + transactions/savepoints + replica validation + restore drill + shakedown |
| Rule of Three | EXPLAIN plan + ANALYZE timing + production telemetry MUST agree before deploying a query change |

Following these rules produces SQL code and database schemas that are performant, maintainable, secure, and resilient. The database enforces integrity constraints that protect data regardless of application behavior. Queries execute efficiently because indexing strategy matches access patterns. Migrations deploy safely because they're tested and reversible.

---
[Back to Overview](./OVERVIEW.md)
