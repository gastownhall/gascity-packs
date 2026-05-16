# Connection Management

### Connection Fundamentals

Each Redis connection consumes memory on server and client. Connection establishment involves TCP handshake and optional TLS negotiation — milliseconds of latency before the first command executes.

**Connection cost breakdown:**

| Phase | Cost (within region) |
|:------|:---------------------|
| TCP handshake | ~1 round trip (0.5–2ms) |
| TLS negotiation | 1–2 additional round trips (1–4ms) |
| AUTH command | 1 round trip |
| **Total new connection** | **3–8ms before first useful command** |

Applications that create connections per request waste this latency on every operation.

### Connection Pooling

All production Redis clients must use connection pooling.

**Pool sizing formula:**

```text
pool_size = (peak_operations_per_second * average_operation_latency_seconds) * 1.5
```

Example: 1000 ops/sec with 2ms average latency = 1000 × 0.002 × 1.5 = **3 connections minimum**.

**Pool configuration principles:**

- **Min connections** — keep warm connections ready; eliminates cold-start latency.
- **Max connections** — hard cap prevents runaway connection creation.
- **Idle timeout** — release unused connections; Redis may close idle connections server-side.
- **Connection validation** — test connections before use; detect broken connections early.

### Multiplexing

Modern Redis clients (StackExchange.Redis for .NET, ioredis for Node.js, redis-py with hiredis) support multiplexing — multiple concurrent operations over a single TCP connection.

| Benefits | When multiplexing is insufficient |
|:---------|:----------------------------------|
| Fewer total connections required | Blocking ops (`BLPOP`, `BRPOP`) require dedicated connections |
| Better TCP window utilization | Pub/Sub subscriptions require dedicated connections |
| Reduced connection overhead | Very high throughput may benefit from multiple connections to parallelize I/O |

### StackExchange.Redis Connection Management (.NET)

StackExchange.Redis uses a multiplexed `ConnectionMultiplexer`:

- Create **ONE** `ConnectionMultiplexer` instance per Redis endpoint.
- Register as singleton in dependency injection.
- Reuse across all requests and threads.
- **Never create per-request** — the object is designed for reuse.

```csharp
// StackExchange.Redis singleton pattern
public class RedisConnection
{
    private static readonly Lazy<ConnectionMultiplexer> lazyConnection =
        new Lazy<ConnectionMultiplexer>(() =>
        {
            return ConnectionMultiplexer.Connect(new ConfigurationOptions
            {
                EndPoints = { "cache.redis.cache.windows.net:6380" },
                Password = GetSecretFromVault("redis-password"),
                Ssl = true,
                AbortOnConnectFail = false,
                ConnectRetry = 3,
                ConnectTimeout = 5000,
                SyncTimeout = 5000,
                AsyncTimeout = 5000,
                AllowAdmin = false
            });
        });
    public static ConnectionMultiplexer Connection => lazyConnection.Value;
}
```

| Option | Default | Notes |
|:-------|:--------|:------|
| `connectTimeout` | 5000ms | Time to establish connection |
| `syncTimeout` | 5000ms | Time for synchronous operations |
| `asyncTimeout` | 5000ms | Time for async operations |
| `connectRetry` | 3 | Retry attempts on connection failure |
| `abortOnConnectFail` | false | False for resilient applications |
| `ssl` | true | Required for Azure Cache for Redis |
| `allowAdmin` | false | True only when administrative commands needed |

**Connection string format:**

```text
{cachename}.redis.cache.windows.net:6380,password={accesskey},ssl=True,abortConnect=False
```

### Connection Resilience

Redis connections fail. Networks partition. Nodes restart. Applications must handle connection failures gracefully:

- **Retry with backoff** — transient failures resolve quickly; retry before failing.
- **Circuit breaker** — repeated failures indicate systemic problems; stop hammering a dead endpoint.
- **Fallback to database** — cache misses are normal; application continues without cache.
- **Health checks** — monitor connection state; alert on persistent failures.

### Azure-Specific Connection Considerations

- **Firewall rules** — Azure Cache for Redis has a firewall; client IPs must be allowed or VNet integrated.
- **Private endpoint** — recommended for production; traffic never traverses public internet.
- **DNS resolution** — Azure cache endpoints resolve to Azure-internal IPs when accessed from VNet.
- **Idle connection timeout** — Azure may close idle connections after ~10 minutes; configure client keep-alive.

---
[Back to Overview](./OVERVIEW.md)
