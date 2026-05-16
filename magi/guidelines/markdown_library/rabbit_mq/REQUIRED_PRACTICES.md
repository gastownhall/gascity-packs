# Required Practices

### Always Do

- Enable and handle publisher confirms.
- Use manual acknowledgment with explicit `ack`/`nack`.
- Configure dead letter exchanges for all production queues.
- Set queue length limits with appropriate overflow behavior.
- Implement idempotent message processing.
- Use quorum queues for replicated workloads.
- Monitor queue depth, consumer count, and memory usage.
- Encrypt connections with TLS in production.
- Implement connection and channel recovery.
- Set meaningful message properties (`message_id`, `type`, `timestamp`).
- Use prefetch to control consumer load.
- Configure heartbeats appropriate to network conditions.
- Implement retry limits with dead-lettering for poison messages.
- Version message schemas for backward compatibility.
- Test failover scenarios before they occur in production.
- Run a §16 shakedown after every change to topology, publishers, consumers, policies, vhosts, users, or cluster configuration.

---
[Back to Overview](./OVERVIEW.md)
