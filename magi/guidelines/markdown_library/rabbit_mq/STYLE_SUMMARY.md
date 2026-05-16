# Style Summary

| Element | Required Style |
|:--------|:---------------|
| Acknowledgment | Manual; ack after successful processing |
| Publisher Confirms | Enabled; handle confirms/nacks explicitly |
| Queue Durability | Durable queues with persistent messages for production |
| Queue Type | Quorum for HA; classic only when measured necessary |
| Prefetch | Set based on consumer throughput; never unlimited |
| Dead Letters | DLX configured on all queues; DLQ monitored |
| Connections | Long-lived; one per application instance |
| Channels | Per-thread or pooled with synchronization |
| Message IDs | Unique identifier on every message |
| Serialization | Binary formats for volume; JSON for debugging |
| Naming | Dot-delimited hierarchies: `domain.purpose.qualifier` |
| Authentication | LDAP or OAuth for production; no shared credentials |
| TLS | Required for all production connections |
| Monitoring | Prometheus metrics; alerts on queue depth and memory |
| Clustering | Minimum 3 nodes with quorum queues for production |
| Partitions | `pause_minority` default; runbook for recovery |
| Retry | Bounded retries with exponential backoff; eventual dead-letter |
| Message Size | Under 128KB; external storage for larger payloads |
| Shakedown | Canary publish→confirm→deliver→ack→DLX round-trip; pass / fail-blocking / fail-nonblocking / inconclusive |
| Defense in Depth | Quorum + confirms + manual ack + DLX + monitoring + 3-node cluster + definition backups |
| Rule of Three | Three-node cluster minimum — one fails with no message loss and no availability impact |

---
[Back to Overview](./OVERVIEW.md)
