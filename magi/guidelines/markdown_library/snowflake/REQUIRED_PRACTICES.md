# Required Practices

### Always Do

- Configure auto-suspend on every warehouse (60–300 seconds default).
- Use dedicated warehouses for distinct workloads (ETL, BI, ad-hoc).
- Enable resource monitors with suspend triggers before going to production.
- Examine Query Profile for expensive queries before optimization.
- Tag objects and queries for cost attribution.
- Use role-based access control with principle of least privilege.
- Pin critical query execution to specific warehouse sizes via session parameters when needed.
- Document clustering key selection rationale.
- Version control all DDL and transformation logic.
- Test migrations in non-production environments with cloned data.
- Use Snowflake Scripting or Python procedures for complex orchestration.
- Define file formats explicitly and reuse across load operations.
- Set appropriate Time Travel retention per table based on recovery requirements.
- Monitor serverless feature consumption (clustering, Snowpipe, search optimization).
- Use secure views for data sharing.
- Implement CI/CD for schema and transformation deployments.
- Create alerts for operational anomalies (credit spikes, failed tasks, login failures).
- Use `MERGE` for upsert patterns to maintain idempotency.
- Document stream-task relationships and consumption patterns.
- Apply masking policies to sensitive columns in all environments.
- Run a §20 shakedown after every DDL apply against any environment.

---
[Back to Overview](./OVERVIEW.md)
