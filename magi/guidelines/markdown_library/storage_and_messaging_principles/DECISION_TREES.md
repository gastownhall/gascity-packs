# Decision Trees

### Primary Data Store Selection

```
Is data relational with complex relationships?
├── Yes: Need ACID transactions across entities?
│   ├── Yes → SQL Database (SQL Server, PostgreSQL)
│   └── No: Scale beyond single node?
│       ├── No → SQL Database
│       └── Yes: Global distribution needed?
│           ├── Yes → Cosmos DB (consider trade-offs)
│           └── No → SQL with read replicas or sharding
└── No: What is the primary access pattern?
    ├── Key-Value only → Redis (volatile) or Cosmos DB (persistent)
    ├── Document with queries → Cosmos DB
    ├── Time-series → Time-series DB or Cosmos DB
    ├── Large files/blobs → Blob Storage
    └── Graph traversal → Cosmos DB Gremlin API or Neo4j
```

### Caching Layer Selection

```
Do you need caching?
├── No: Single-instance, low latency OK, data small → In-process cache
└── Yes: Shared across instances?
    ├── No: Use IMemoryCache or similar in-process cache
    └── Yes: What are latency requirements?
        ├── Sub-millisecond critical → Redis
        └── 10-50ms acceptable: High availability needed?
            ├── Yes → Redis (Standard/Premium tier)
            └── No: Cost sensitive?
                ├── Yes → Table Storage or Cosmos DB serverless
                └── No → Redis
```

### Message Broker Selection

```
Need async messaging?
├── Simple decoupling, cost-sensitive → Storage Queues
├── Need dead-letter, scheduling, sessions → Service Bus
├── Complex routing, open protocols → RabbitMQ
├── Event streaming, replay, high throughput → Event Hubs / Kafka
└── In-process only → Channels or ConcurrentQueue
```

---
[Back to Overview](./OVERVIEW.md)
