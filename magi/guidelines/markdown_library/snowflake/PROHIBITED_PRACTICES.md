# Prohibited Practices

### Never Do

- Run queries without warehouse auto-suspend configured; idle warehouses burn credits continuously.
- Use `ACCOUNTADMIN` for routine operations; create and use functional roles.
- Store sensitive credentials in Snowflake tables; use secrets management integration.
- Ignore Query Profile; optimization without measurement is guesswork.
- Create materialized views without confirmed query patterns; they have maintenance costs.
- Use `SELECT *` in production queries; request only needed columns.
- Set maximum Time Travel retention universally; match retention to recovery requirements.
- Deploy changes directly to production; use promotion pipelines with validation.
- Ignore clustering depth on large tables; degraded clustering compounds query costs.
- Create warehouses without resource monitors; uncontrolled spending is organizational risk.
- Use default file formats for complex data; misconfigured formats cause silent data issues.
- Grant privileges directly to users; grant to roles, assign users to roles.
- Run transformations on load warehouses; isolate ETL from query workloads.
- Neglect stream consumption; unconsumed streams grow unboundedly.
- Use JavaScript UDFs in row-by-row hot paths; initialization overhead kills performance.
- Embed business logic in views without documentation; views become unmaintainable black boxes.
- Create reader accounts without understanding you pay for their compute.
- Configure auto-clustering on small tables; overhead exceeds benefit.
- Use `COPY INTO` without `ON_ERROR` handling; silent failures create data gaps.
- Ignore failed tasks; no automatic retry means missed processing windows.
- Skip the §20 shakedown after a triggering DDL change.
- Run shakedown against a zero-copy clone made before the DDL applied.

---
[Back to Overview](./OVERVIEW.md)
