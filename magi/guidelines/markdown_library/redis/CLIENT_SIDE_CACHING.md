# Client-Side Caching

### Overview

Redis 6.0+ introduced server-assisted client-side caching (tracking). The server tracks which keys each client has cached locally and sends invalidation messages when those keys change.

| Mode | Behavior |
|:-----|:---------|
| Default | Server tracks exact keys client accessed |
| Broadcasting | Server broadcasts all invalidations; client filters locally |
| OPTIN | Client explicitly tracks specific keys |
| OPTOUT | Client tracks all keys except explicitly excluded |

### Architecture

1. Client issues `GET` command.
2. Server returns value; optionally registers tracking.
3. Client stores value in local memory.
4. Subsequent reads return from local cache (no network).
5. When key changes, server pushes invalidation.
6. Client evicts local entry; next read fetches from server.

**Invalidation delivery:**

- Requires dedicated connection for RESP3 push notifications.
- Or uses Pub/Sub channel for RESP2 compatibility.
- Client must maintain listener for invalidation messages.

### Implementation Considerations

| Concern | Guidance |
|:--------|:---------|
| Local cache sizing | Memory consumed in application process; size based on working set, not total dataset; LRU or similar eviction locally |
| TTL synchronization | Local cache TTL ≤ server TTL; 30–60 seconds is reasonable for most scenarios |
| Connection requirements | One connection for tracking (receives invalidations); separate for commands if RESP2; RESP3 simplifies with push notifications |
| Library support | StackExchange.Redis 2.6+; Lettuce (Java); redis-py limited support — verify before relying on it |

### When to Use

| Appropriate | Avoid |
|:------------|:------|
| Hot keys accessed repeatedly within same instance | Dataset doesn't fit in application memory |
| Configuration data read frequently, changed rarely | Keys change frequently (invalidation traffic exceeds benefit) |
| Reference data (lookup tables, enums) with low change frequency | Application instances are short-lived (serverless, scale-to-zero) |
| Workloads where microsecond latency matters | Read patterns are random without hot spots |

### Local Cache Without Server Tracking

For scenarios where server-assisted caching isn't available, implement two-tier caching:

| Tier | Implementation |
|:----:|:---------------|
| 1 | In-process memory cache (`IMemoryCache` in .NET, LRU cache in other languages) |
| 2 | Redis |

**Access pattern:** check local cache → if miss, check Redis → if miss, query data source → populate both caches.

**Invalidation options:**

- **Time-based** — short local TTL (10–60 seconds), longer Redis TTL.
- **Event-based** — Pub/Sub notification from writer to all instances.
- **Hybrid** — short TTL with Pub/Sub for immediate critical invalidations.

---
[Back to Overview](./OVERVIEW.md)
