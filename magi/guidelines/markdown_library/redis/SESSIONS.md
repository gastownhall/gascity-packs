# Session Management and Sticky Sessions

### Session Storage in Redis

Redis is a common session store for distributed applications:

- Fast access (sub-millisecond).
- Built-in expiration (TTL matches session timeout).
- Atomic operations (no read-modify-write races).
- Shared across all application instances.

**Session data structure:**

- String with serialized session object — simple but requires full deserialization.
- Hash with session fields — enables partial reads and atomic field updates.

### Sticky Sessions vs Distributed Sessions

| Approach | Behavior | Failure mode |
|:---------|:---------|:-------------|
| Sticky sessions (session affinity) | Load balancer routes user to same server; state lives in process memory | Server crash, scale down, deployment, or LB reconfigure → session lost |
| Distributed sessions with Redis | Any instance serves any request; session retrieved from Redis on each request | Redis failure (mitigated with retry + fallback) |

### Hybrid Session — Sticky + Redis Backup

Hybrid approach provides best of both worlds: sticky session routes requests to same instance for L1 cache hits; session changes write through to Redis; if sticky session breaks, new instance loads from Redis.

```csharp
public class HybridSessionProvider
{
    private readonly IMemoryCache _localCache;
    private readonly IConnectionMultiplexer _redis;
    private readonly TimeSpan _localTtl = TimeSpan.FromSeconds(5);
    private readonly TimeSpan _redisTtl = TimeSpan.FromMinutes(30);

    public async Task<SessionData> GetSessionAsync(string sessionId)
    {
        // L1: Check local cache
        if (_localCache.TryGetValue(sessionId, out SessionData cached))
            return cached;

        // L2: Check Redis
        var db = _redis.GetDatabase();
        var data = await db.HashGetAllAsync($"session:{sessionId}");
        if (data.Length == 0)
            return null;

        var session = DeserializeSession(data);

        // Populate L1 cache
        _localCache.Set(sessionId, session, _localTtl);

        // Extend Redis TTL (sliding expiration)
        await db.KeyExpireAsync($"session:{sessionId}", _redisTtl);
        return session;
    }

    public async Task SetSessionAsync(string sessionId, SessionData session)
    {
        // Write-through to both layers
        _localCache.Set(sessionId, session, _localTtl);

        var db = _redis.GetDatabase();
        var hash = SerializeSession(session);

        var tran = db.CreateTransaction();
        tran.HashSetAsync($"session:{sessionId}", hash);
        tran.KeyExpireAsync($"session:{sessionId}", _redisTtl);
        await tran.ExecuteAsync();
    }
}
```

### Session Data Guidelines

- **Keep sessions small** — store identifiers, not full objects (user ID, not user object). Reference data lives in dedicated caches with proper TTL. Large sessions cause latency and memory pressure.
- **Structured session data** — use hash type for sessions with multiple fields:

```text
HSET session:abc123 userId 12345 cartId cart:67890 lastAccess 1700000000
```

- **Session TTL** — absolute (fixed from creation), sliding (extends on each access), or maximum lifetime (hard cap).
- **Sliding timeout implementation** — pipeline `GET` + `EXPIRE` for single round trip.

### Sticky Session Configuration

| Platform | Mechanism |
|:---------|:----------|
| Azure Application Gateway | Cookie-based affinity; backend pool instance encoded in cookie |
| Azure Load Balancer | Source IP affinity (tuple-based); less reliable than cookie-based |
| Kubernetes (AKS) | Service `sessionAffinity: ClientIP` or Ingress controller cookie-based affinity |

**Best practice:** always implement Redis session storage **even with sticky sessions enabled**. Treat sticky sessions as optimization, not requirement.

### Session Security

| Concern | Practice |
|:--------|:---------|
| Session ID entropy | Cryptographically random, minimum 128 bits |
| Session fixation | Regenerate session ID on authentication |
| Sensitive data | Encrypt before storing; Redis is not encrypted at rest by default (Azure provides this in Premium+) |
| Session invalidation | Explicit `DELETE` on logout — don't rely solely on TTL |

---
[Back to Overview](./OVERVIEW.md)
