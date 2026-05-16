# Shakedown — Integration Validation

### Definition

A Redis shakedown is the **first controlled set of end-to-end round-trips across every Redis primitive the service actually uses**, executed against the real connection pool after any change that touches cluster topology, TLS, ACLs, replication, eviction policy, persistence, modules, or Lua scripts. The shakedown answers one question: **does the service's Redis access path actually work, end to end, against this instance, with the declared semantics intact?**

| Distinct from | Difference |
|:--------------|:-----------|
| Health check | Issues `PING`; shakedown executes `SET`/`GET`, pub/sub, cluster routing, and failover round-trips against the live client pool |
| Benchmark | Drives `redis-benchmark` at high QPS; shakedown runs a handful of known-good operations and verifies the values come back intact |

### Mandatory Triggers

- First-ever deployment of a Redis client, cache namespace, or consumer group.
- Tier migration (Basic → Standard → Premium → Enterprise).
- Cluster topology change: shard count increase, shard rebalance, hash slot migration.
- Failover, replica promotion, or sentinel quorum reconfiguration.
- Persistence configuration change: RDB snapshot interval, AOF fsync policy, hybrid persistence.
- Eviction policy change (`noeviction`, `allkeys-lru`, `volatile-lfu`, etc.).
- ACL rule modification affecting the service account.
- TLS certificate rotation or cipher suite change.
- Redis module enablement or version upgrade (RedisJSON, RedisSearch, RedisTimeSeries).
- Lua script deployment or `EVALSHA` script cache change.
- Redis version upgrade or Azure Cache for Redis SKU change.
- Recovery after a failover event or memory-pressure eviction incident.

### Non-Triggers

- Routine cache reads and writes against an unchanged instance.
- Application restart with identical client configuration.
- Adjusting TTL values within the validated range.
- Adding a new cache key pattern that uses the same primitive and hash tag convention.

### Validation Categories

1. **Connection-pool round-trip** — `ConnectionMultiplexer` (or equivalent) instantiates with `AbortOnConnectFail=false` and `ConnectRetry` configured; `PING` returns `PONG` from the actual pool used by the service; `SET canary:{timestamp}` then `GET canary:{timestamp}` round-trips with value intact; pool does not exhaust under a small burst.
2. **Primitive coverage** — string `SET`/`GET` with `EX` TTL; hash `HSET`/`HGETALL`; list `LPUSH`/`RPOP`; sorted set `ZADD`/`ZRANGE`; stream `XADD`/`XREAD` if Streams are used. Only primitives actually used by the service are in scope.
3. **Pub/sub and keyspace notifications** — canary `SUBSCRIBE` on a dedicated channel receives a `PUBLISH` round-trip within latency budget; keyspace notification events fire for the configured `notify-keyspace-events` bitmap if relied upon.
4. **Cluster routing** — `CLUSTER NODES` reports every shard reachable from the client; hash-tagged canary keys `{shakedown}:a`, `{shakedown}:b`, `{shakedown}:c` land on the same slot and shard; `MOVED` and `ASK` redirections resolve transparently during in-flight slot migration; multi-key canary operations within a hash tag execute atomically.
5. **Failover and replication** — replica `SYNC` state is connected for every replica reported by `INFO replication`; a forced failover (Azure Cache reboot or Sentinel failover) is transparent to the client connection pool with retry-with-backoff; canary `SET` issued during the failover window eventually commits on the new primary.
6. **Persistence round-trip** — `BGSAVE` completes without error and `last_save_time` advances; AOF fsync policy holds; canary key written before a controlled restart is readable after restart (persistence-enabled tiers only).
7. **Eviction under pressure** — with `maxmemory-policy` set, a canary write under synthetic memory pressure triggers eviction of the declared key class; `evicted_keys` increments; service handles cache-miss path; `noeviction` returns `OOM` and the client surfaces it.
8. **Lua script execution** — `EVAL` of the canary compare-and-swap script returns the expected result; `EVALSHA` hits the script cache after the first `EVAL`; `SCRIPT EXISTS` confirms presence; all keys declared in `KEYS` map to the same slot in clustered deployments.
9. **Module commands** — `JSON.SET`/`JSON.GET` round-trip a canary document if RedisJSON is enabled; `FT.CREATE` index reachable and `FT.SEARCH` returns the canary document if RedisSearch is enabled; `TS.ADD`/`TS.RANGE` round-trip a canary sample if RedisTimeSeries is enabled.
10. **TLS and ACL** — TLS handshake succeeds on port 6380 with declared certificate chain and cipher suite; `AUTH` with the service ACL user succeeds; `ACL WHOAMI` reports the expected username; service ACL user has the declared key pattern and command category permissions; a forbidden command returns `NOPERM`.

### Execution Principles

- **Conservative** — one canary per primitive the service uses, with known keys and known values. Nothing else.
- **Progressive stress** — connect, `SET`/`GET`, then primitives, then cluster routing, then failover, then eviction, then modules. Stop at the first failure and diagnose.
- **Controlled environment** — run against the target instance from the target network path, using the target ACL user. Not against a local Redis container with different configuration.
- **Observable execution** — capture client pool metrics, `INFO` output before and after, `CLUSTER NODES` output, full command log at DEBUG.
- **Known-good inputs** — canary keys under a reserved `shakedown:` namespace with deterministic values and pre-computed hashes.
- **No optimization during shakedown** — do not retune pool size, timeouts, or eviction policy while canaries are in flight.

### Execution Pattern

1. Confirm preflight: instance reachable, TLS handshake succeeds, ACL `AUTH` succeeds, `CLUSTER NODES` returns all shards if clustered.
2. Execute connection pool `PING` and a basic `SET`/`GET` canary round-trip.
3. Execute one canary per primitive the service uses (string, hash, list, sorted set, stream).
4. Execute pub/sub canary on a dedicated `shakedown:` channel.
5. Execute Lua script canary (`EVAL` then `EVALSHA`) if Lua is used.
6. Execute module command canaries if modules are enabled.
7. Execute controlled failover or persistence round-trip if the change touched replication or persistence.
8. Record all observations; classify the shakedown result.

### Canary Runner

Minimal canary runner executed from the service against the target Redis. Uses the service's actual connection pool and ACL user.

```python
# Shakedown canary runner
import redis
import time
import uuid

def shakedown(pool: redis.ConnectionPool) -> dict:
    client = redis.Redis(connection_pool=pool)
    canary_id = f"shakedown:{uuid.uuid4()}"
    results = {}

    # 1. Connection pool round-trip
    results["ping"] = client.ping()

    # 2. String primitive
    client.set(canary_id, "canary-value", ex=60)
    results["string"] = client.get(canary_id) == b"canary-value"

    # 3. Hash primitive
    client.hset(f"{canary_id}:hash", mapping={"field": "value"})
    client.expire(f"{canary_id}:hash", 60)
    results["hash"] = client.hget(f"{canary_id}:hash", "field") == b"value"

    # 4. Cluster shard reachability
    try:
        nodes = client.cluster("NODES")
        results["cluster_nodes"] = len(nodes.splitlines()) > 0
    except redis.ResponseError:
        results["cluster_nodes"] = "not-clustered"

    # 5. Pub/sub round-trip
    pubsub = client.pubsub()
    pubsub.subscribe(f"{canary_id}:channel")
    time.sleep(0.05)
    client.publish(f"{canary_id}:channel", "canary-event")
    message = pubsub.get_message(timeout=1.0)
    while message and message["type"] != "message":
        message = pubsub.get_message(timeout=1.0)
    results["pubsub"] = message is not None and message["data"] == b"canary-event"
    pubsub.close()

    # 6. ACL identity
    results["acl_whoami"] = client.execute_command("ACL", "WHOAMI")

    # Cleanup
    client.delete(canary_id, f"{canary_id}:hash")
    return results
```

### Result Classification

| Outcome | Meaning |
|:--------|:--------|
| `pass` | Every canary round-trips with expected value; cluster nodes reachable; pub/sub delivers; ACL identity correct; modules respond — proceed |
| `fail-blocking` | Connection pool cannot connect; TLS handshake fails; ACL denies the service user; primitive returns wrong value; cluster shard unreachable; forced failover loses the canary write — halt, fix root cause, re-run full shakedown |
| `fail-nonblocking` | Canary latency exceeds p99 budget but succeeds; `evicted_keys` unexpectedly nonzero; non-critical fragmentation warning — log to issue tracker with full diagnostic context, proceed with caution |
| `inconclusive` | Target instance is mid-failover or mid-rebalance during the window — adjust and re-run the specific validation |

### Required Artifacts

- Execution log with per-canary command, response, and latency.
- Result summary: connection pool, primitive coverage, pub/sub, cluster routing, failover, persistence, eviction, Lua, modules, TLS, ACL.
- Issue list: every anomaly classified blocking, non-blocking, or deferred, with `INFO` excerpts and client log lines.
- Environment snapshot: Redis version, tier, shard count, `maxmemory`, `maxmemory-policy`, persistence mode, enabled modules, ACL user rules, TLS certificate fingerprint, effective `ConnectionMultiplexer` configuration.

### Anti-Patterns

- Skipping shakedown after a "small" ACL change that touched command category permissions.
- Running shakedown against a local Redis container instead of the target Azure Cache for Redis instance.
- Treating shakedown as a comprehensive cache integration suite with hundreds of key patterns.
- Tuning pool size or timeouts while canaries are in flight.
- Running shakedown without capturing `INFO` and `CLUSTER NODES` output.
- Omitting the eviction canary when the change touched `maxmemory-policy`.

---
[Back to Overview](./OVERVIEW.md)
