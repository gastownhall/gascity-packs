# Prohibited Practices

### Never Do

- Use `SELECT *` in production code; it breaks when schema changes and defeats index-only scans.
- Concatenate user input into SQL strings; parameterize everything.
- Use implicit type conversions; explicit `CAST` or `CONVERT` prevents surprises.
- Store dates as strings; use proper temporal types.
- Store JSON for relational data that fits normal schema design.
- Create tables without primary keys.
- Use triggers for complex business logic; they hide behavior and complicate debugging.
- Execute DDL in application code at runtime; schema changes belong in migrations.
- Use cursors for set-based operations; rewrite as single statements.
- Ignore execution plans; if you haven't looked at the plan, you don't know if the query is efficient.
- Rely on implicit transaction behavior; explicit `BEGIN`, `COMMIT`, `ROLLBACK`.
- Use `NOLOCK` (SQL Server) or `READ UNCOMMITTED` as a performance fix; fix the underlying contention.
- Leave nullable columns without explicit business justification.
- Create redundant indexes that duplicate leading columns of existing indexes.
- Deploy migrations without testing rollback scripts.
- Shrink database files in normal operations; it causes fragmentation.
- Use `sp_` prefix for user procedures in SQL Server (reserved for system procedures).
- Create circular foreign key dependencies.
- Store passwords in plain text or reversible encryption.
- Use `FLOAT` or `MONEY` types for financial calculations.
- Run ad-hoc DDL directly in production; use migration scripts.
- Use implicit joins with comma-separated tables; always use explicit `JOIN ... ON`.
- Use `WHILE` loops or cursors for set operations.
- Use global temporary tables; use local temp tables.
- Use nested transactions; use savepoints.
- Use functions in `WHERE` clauses on indexed columns.
- Use reserved words as identifiers.
- Skip the §Shakedown after a triggering change.
- Run shakedown against an in-memory or SQLite stand-in when production is a different engine.

---
[Back to Overview](./OVERVIEW.md)
