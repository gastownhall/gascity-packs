# Redis

### What It Is

Redis is an in-memory data structure store used as a cache, message broker, and database. It stores data in memory for sub-millisecond access and supports various data structures (strings, hashes, lists, sets, sorted sets, streams).

### Core Strengths

- **Speed**: Sub-millisecond latency for reads and writes; data is in memory
- **Rich Data Structures**: Not just key-value; supports lists, sets, sorted sets, hashes, streams, geospatial
- **Atomic Operations**: INCR, LPUSH, ZADD are atomic; enables counters, rate limiters, queues
- **Pub/Sub**: Built-in publish/subscribe messaging
- **Lua Scripting**: Complex atomic operations via server-side Lua scripts
- **TTL Support**: Automatic expiration of keys; ideal for caching and sessions
- **Cluster Mode**: Horizontal scaling across multiple nodes

### Core Weaknesses

- **Memory Bound**: Data must fit in RAM; expensive for large datasets
- **Durability Trade-offs**: Persistence options (RDB, AOF) have trade-offs between durability and performance
- **No Complex Queries**: No SQL, no secondary indexes (without Redis Search), no JOINs
- **Eventual Consistency in Cluster**: Replication is asynchronous; writes can be lost on failover
- **Operational Complexity**: Cluster mode requires careful management of slots and replication

### Ideal Use Cases

- **Caching**: Cache database results, API responses, computed values
- **Session Storage**: User sessions with automatic expiration
- **Rate Limiting**: Sliding window counters using sorted sets
- **Leaderboards**: Sorted sets for real-time rankings
- **Real-time Analytics**: Counters, HyperLogLog for unique counts
- **Distributed Locks**: Redlock algorithm for distributed locking
- **Message Queues**: Lists or streams for lightweight queuing
- **Pub/Sub Messaging**: Real-time notifications, chat

### Avoid When

- Data must survive complete infrastructure failure (use as cache, not primary store)
- Dataset exceeds available memory budget
- Complex queries or secondary access patterns are required
- Strong consistency is required
- Durability is paramount (financial transactions)

### Data Structure Selection

| Structure       | Use Case                    | Example                                             |
|-----------------|-----------------------------|-----------------------------------------------------|
| **String**      | Simple values, counters     | `SET user:123:name "John"`, `INCR page:views`       |
| **Hash**        | Objects with fields         | `HSET user:123 name "John" email "j@x.com"`         |
| **List**        | Queues, recent items        | `LPUSH queue:emails msg`, `LRANGE recent:posts 0 9` |
| **Set**         | Unique collections, tags    | `SADD user:123:roles admin editor`                  |
| **Sorted Set**  | Leaderboards, time-series   | `ZADD leaderboard 1000 user:123`                    |
| **Stream**      | Event logs, message queues  | `XADD events * type purchase amount 50`             |
| **HyperLogLog** | Unique counts (approximate) | `PFADD unique:visitors user:123`                    |

### Caching Patterns

**Cache-Aside (Lazy Loading)**:

	1.	Application checks cache
	2.	If miss, query database
	3.	Store result in cache with TTL
	4.	Return result

**Write-Through**:

	1.	Application writes to cache
	2.	Cache writes to database (synchronously)
	3.	Return success

**Write-Behind (Write-Back)**:

	1.	Application writes to cache
	2.	Cache acknowledges immediately
	3.	Cache writes to database asynchronously

**Cache Invalidation**:
- TTL-based: Set expiration on write; accept staleness window
- Event-based: Invalidate cache when source data changes
- Version-based: Include version in cache key; change version on update

### Sticky Sessions, Pod Churn, and Cache Fragmentation

When sticky sessions (session affinity) are enforced, traffic for a user tends to land on the same application instance. This often hides architectural problems until the cluster scales, pods roll, or routing changes.

**What breaks in dynamic clusters (Kubernetes, autoscaling, rolling updates)**:
- **Per-instance memory caches diverge**: Each pod has its own cache; values differ based on which requests it saw.
- **Cache hit rate becomes accidental**: A user pinned to pod A is “warm,” but pod B is “cold,” causing inconsistent latency and load spikes.
- **Cache fragmentation**: Same keys exist in multiple pods, wasting memory and multiplying invalidation complexity.
- **State evaporates on reschedule**: Pods are ephemeral; cache disappears on restart, eviction, or node drain.
- **Sticky sessions are not stable**: Ingress/controller behavior, deployment rollouts, pod restarts, and scaling events can remap users at any time.
- **Bug masking**: “Works in prod most of the time” because affinity keeps sessions warm; fails under churn, failover, or partial outages.

### How Redis Resolves Sticky-Session Cache Failure Modes

Redis provides a shared, external cache and session store that survives pod churn and eliminates per-instance divergence.

**Primary benefits**:
- **Single shared cache across pods**: Any pod can read/write the same keys; cache content is no longer tied to a specific instance.
- **Consistent behavior under scaling**: New pods start “cold” only in CPU/memory terms, not in cached data; hit rate stays stable.
- **Centralized invalidation**: One invalidation affects all pods because the cached entry is shared.
- **Externalized session state**: Sessions are not bound to one pod; sticky sessions become optional rather than required.
- **Backpressure and protection primitives**: Atomic counters, locks, and Lua scripts enable safe stampede control and rate limiting in distributed systems.

**What to externalize into Redis**:
- **Sessions**: `session:{session_id}` with TTL (server-side sessions) or `user-session:{user_id}` if keyed by identity.
- **Auth artifacts**: Token introspection results, permission sets, feature flags (with TTL/versioning).
- **Computed results**: Expensive aggregates, enriched objects, rendered templates, serialized response payloads.

### Recommended Patterns for Kubernetes and Autoscaling

**1) Replace sticky sessions with shared session storage**
- Store session state in Redis (TTL per session).
- Configure application instances to be stateless (no in-memory session dependency).
- Keep sticky sessions off unless you have a hard dependency you cannot remove.

**2) Two-level cache (optional, controlled)**
- L1: small in-memory cache per pod (very short TTL, bounded size) for ultra-hot keys.
- L2: Redis as authoritative cache layer.
- Use L1 only when you can tolerate small staleness windows and have a clear eviction policy; Redis remains the shared source.

**3) Stampede protection for hot keys**
- Use a Redis lock or “single-flight” key to prevent 100 pods from recomputing the same value after expiration.
- Add TTL jitter to avoid synchronized expirations: e.g., base TTL + random(0..N seconds).
- Prefer serving slightly stale data for a short window rather than thundering-herd the database (stale-while-revalidate pattern).

**4) Event-driven invalidation (when correctness matters)**
- On data change, publish an invalidation event (Pub/Sub or Streams) with the key(s) or namespace version.
- Pods subscribe and purge local L1 entries (if L1 exists) while Redis keys are deleted or versioned.
- For high fan-out or durability needs, prefer Streams over Pub/Sub.

**5) Versioned keys to simplify invalidation**
- Namespace with versions: `product:v3:{id}` or `product:{id}:v{version}`.
- When source data changes, bump version in a small “version key” and let old entries die via TTL.
- Works well when invalidation lists are large or hard to compute.

### Key Design for Multi-Instance Deployments

**Key conventions that prevent collisions and enable bulk invalidation**:
- Include environment/tenant: `prod:{tenant}:...` / `qa:{tenant}:...`
- Include domain context: `cache:product:{id}`, `session:{sid}`, `authz:{user_id}`
- Keep values small and predictable; compress only when it materially reduces bandwidth.

**TTL guidance**:
- Sessions: TTL aligned with idle timeout; refresh TTL on activity.
- Cache entries: TTL based on data volatility; prefer minutes over hours unless the data is truly static.
- Add jitter for high-volume keys to smooth expiration waves.

### Operational Notes for Redis in This Scenario

- **High availability**: Use replication and managed failover (or sentinel/managed offering) to avoid single-node cache outages.
- **Time-outs and fallbacks**: Redis must have strict client timeouts; cache failures should degrade gracefully (hit database, serve partial, or fail fast based on endpoint criticality).
- **Observe eviction**: Evictions in a shared cache affect all pods simultaneously; monitor memory, evictions, and latency.
- **Right-size pool/connections**: Many pods means many Redis clients; enforce connection pooling and limits.
- **Avoid per-pod key churn**: Do not embed pod identity in keys; pod churn should not create orphaned namespaces.

### Common Anti-Patterns

- Using Redis as primary database without backup strategy
- Storing large values (>100KB) that cause network latency
- Not setting TTLs on cache entries (memory leak)
- Blocking commands (BLPOP) without timeouts
- Storing sensitive data without encryption (at-rest and in-transit)
- Not monitoring memory usage and eviction rates
- Using Redis for data that requires durability guarantees
- Relying on sticky sessions to “fix” statefulness while still using per-instance memory caches (fails under scaling, rollouts, and pod churn)

---
[Back to Overview](./OVERVIEW.md)
