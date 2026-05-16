# Style Summary

| Decision Type | Key Considerations | Primary Options |
|:--------------|:-------------------|:----------------|
| **Primary Data Store** | Relationships, transactions, query complexity | SQL, Cosmos DB |
| **Caching Layer** | Shared state, latency, data structures | Redis, in-process |
| **File Storage** | Size, access patterns, lifecycle | Blob Storage |
| **Simple Queuing** | Cost, features needed | Storage Queues, Service Bus |
| **Complex Messaging** | Routing, reliability, protocols | RabbitMQ, Service Bus |
| **Event Streaming** | Throughput, replay, consumers | Event Hubs, Kafka |
| **Analytics** | Query complexity, data volume | Synapse, Snowflake |
| **Backup Strategy** | Data criticality, RTO/RPO | Hot standby / Warm PITR / Cold snapshots |
| **Idempotency** | Outbox + Inbox + idempotency keys | Required end-to-end |
| **Shakedown** | Real producer-broker-consumer canary; pass / fail-blocking / fail-nonblocking / inconclusive | After every triggering change |
| **Defense in Depth** | Replication + idempotency + DLQ + monitoring + restore drills + schema evolution + backpressure | All layers active |
| **Rule of Three** | Three replicas (or three durable hops) — survive one failure with quorum preserved | Minimum durability posture |

---

Following this guide produces architectures where each technology is selected based on requirements rather than familiarity or trend. Data access patterns drive storage decisions. Operational complexity is acknowledged and budgeted. Future migrations are anticipated and abstraction layers enable change.

**Apply this selection framework consistently across all storage and messaging decisions. Document the rationale for every technology choice. Review decisions as requirements evolve.**

---
[Back to Overview](./OVERVIEW.md)
