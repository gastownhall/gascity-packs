# Prohibited Practices

### Never Do

- Use auto-acknowledgment for messages that must not be lost.
- Publish without confirms when delivery matters.
- Create unbounded queues without length limits or TTL.
- Share channels across threads without synchronization.
- Embed credentials in application code or configuration.
- Use the default `guest` user in production.
- Deploy single-node clusters for production workloads.
- Ignore dead letter queue growth.
- Create new connections per publish or consume operation.
- Use the `immediate` flag (removed in 3.0) or expect it to work.
- Configure quorum queues with replication factor of 1.
- Let consumers process indefinitely without acknowledging.
- Requeue messages infinitely without retry limits.
- Deploy without monitoring and alerting.
- Use classic mirrored queues (deprecated).
- Assume message ordering across multiple consumers.
- Publish messages larger than 128KB without profiling impact.
- Skip shakedown after a "small" policy change touching HA or DLX routing.
- Run shakedown against in-memory or single-node brokers when the target is multi-node.

---
[Back to Overview](./OVERVIEW.md)
