# Quick Reference Matrix

| Scenario | Recommendation | Reason |
|:---------|:---------------|:-------|
| User Sessions | Redis | Sub-millisecond latency, automatic expiration |
| Product Catalog | Cosmos DB or SQL with Redis Cache | Read-heavy, benefits from caching |
| Financial Transactions | SQL Server / PostgreSQL | ACID requirements, complex queries |
| Log Storage | Blob Storage or Event Hubs | Append-only, high volume, cost-effective |
| Real-time Analytics | Event Hubs + Stream Analytics | High throughput, stream processing |
| Task Queue | Service Bus or Storage Queues | Reliable delivery, poison message handling |
| Chat / Notifications | SignalR with Redis backplane | Real-time, pub/sub pattern |

---
[Back to Overview](./OVERVIEW.md)
