# Required Practices

### Always Do

- Configure `acks=all` and `enable.idempotence=true` on producers.
- Set replication factor to 3 minimum for production topics.
- Use Schema Registry for schema management and evolution.
- Monitor consumer lag and alert on sustained increases.
- Implement graceful shutdown with offset commits.
- Use static consumer group membership in containerized deployments.
- Document topic ownership, schemas, and retention rationale.
- Test consumer behavior with partition rebalances.
- Validate message schemas before production deployment.
- Size partitions for future growth since count cannot decrease.
- Configure dead letter queues for poison message handling.
- Use cooperative rebalancing for consumer groups.
- Implement circuit breakers for external system integration.
- Plan capacity for peak throughput, not average.
- Encrypt data in transit with TLS.
- Apply least-privilege ACLs for all principals.
- Run a §20 shakedown after every change touching topics, producers, consumers, schemas, Connect, ACLs, or broker configuration.

---
[Back to Overview](./OVERVIEW.md)
