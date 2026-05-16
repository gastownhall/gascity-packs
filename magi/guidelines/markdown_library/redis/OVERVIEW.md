# Redis and Azure Cache for Redis Library

These guidelines define strict, performant, and operationally sound patterns for Redis deployments on Azure Cache for Redis.

## Critical Mandates (Read First)
- **Redis Is Ephemeral by Design** — never treat as authoritative data store.
- **Measure Latency at the Application Layer** — not just Redis `INFO`.
- **TTL on All Cached Data** — no infinite-TTL cache entries.
- **TLS Required + Connection Pooling** — single `ConnectionMultiplexer` per endpoint.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [Tier Selection and Architecture](./TIER_SELECTION.md)
3. [Data Modeling and Key Design](./DATA_MODELING.md)
4. [Connection Management](./CONNECTIONS.md)
5. [Caching Strategies and Patterns](./CACHING_STRATEGIES.md)
6. [Client-Side Caching](./CLIENT_SIDE_CACHING.md)
7. [Session Management and Sticky Sessions](./SESSIONS.md)
8. [Pub/Sub and Messaging](./PUBSUB.md)
9. [Clustering and Sharding](./CLUSTERING.md)
10. [Replication and High Availability](./REPLICATION.md)
11. [Persistence Configuration](./PERSISTENCE.md)
12. [Memory Management and Eviction](./MEMORY_EVICTION.md)
13. [Distributed Locking](./DISTRIBUTED_LOCKING.md)
14. [Rate Limiting](./RATE_LIMITING.md)
15. [Lua Scripting](./LUA_SCRIPTING.md)
16. [Cache Stampede Prevention](./STAMPEDE_PREVENTION.md)
17. [Pipeline Optimization](./PIPELINE.md)
18. [Redis Sentinel (Self-Managed)](./SENTINEL.md)
19. [Security Practices](./SECURITY.md)
20. [Performance Optimization](./PERFORMANCE.md)
21. [Monitoring and Diagnostics](./MONITORING.md)
22. [Cost Optimization](./COST.md)
23. [Multi-Tenant and Shared Instance Patterns](./MULTI_TENANT.md)
24. [Integration with Application Caching Layers](./APP_CACHING_INTEGRATION.md)
25. [Shakedown — Integration Validation](./SHAKEDOWN.md)
26. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
27. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
28. [Required Practices](./REQUIRED_PRACTICES.md)
29. [Style Summary](./STYLE_SUMMARY.md)
