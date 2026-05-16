# Prohibited Practices

### Never Do

- Store different partition key strategies in the same container
- Use GUID/random values as partition keys without understanding query implications
- Ignore RU consumption in query development; measure every query
- Create unbounded arrays in documents
- Use cross-partition queries as the primary access pattern
- Store sensitive data unencrypted in fields (beyond at-rest encryption)
- Expose primary keys to client applications
- Use stored procedures for simple CRUD operations
- Ignore 429 rates; they indicate a provisioning problem
- Use `SELECT *` in production queries
- Create one container per entity type mimicking relational tables
- Store timestamps as strings; use ISO 8601 or Unix epoch
- Skip connection reuse; creating clients per request is expensive
- Use strong consistency without understanding latency and availability tradeoffs
- Forget to propagate session tokens in multi-region read-your-writes scenarios
- Skip post-change shakedown after triggers in §17
- Run shakedown against the emulator when production uses multi-region or non-default consistency

### Always Do

- Design partition key based on access patterns before creating containers
- Include partition key in all queries
- Use point reads when ID and partition key are known
- Measure RU consumption for all operations during development
- Configure appropriate retry policies for rate limiting
- Use SDK bulk mode for high-volume ingestion
- Implement optimistic concurrency with ETags for contended updates
- Enable diagnostic logging in production
- Set up alerts for throttling and latency degradation
- Use managed identity or Azure AD authentication for services
- Implement idempotent Change Feed handlers
- Denormalize for read patterns; accept duplication
- Monitor partition sizes and distribution
- Document consistency level choices and their rationale
- Run post-change shakedown after every trigger condition in §17

---
[Back to Overview](./OVERVIEW.md)
