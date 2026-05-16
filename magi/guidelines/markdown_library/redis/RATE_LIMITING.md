# Rate Limiting

### Fixed Window

Simple counter per fixed time window.

```python
def fixed_window_limit(redis, key, limit, window):
    current = redis.incr(key)
    if current == 1:
        redis.expire(key, window)
    return current <= limit
```

Trade-off: bursty at window boundaries (2× limit possible at edge).

### Sliding Window

More accurate rate limiting using sorted sets.

```python
def sliding_window_limit(redis, key, limit, window):
    now = time.time()
    pipeline = redis.pipeline()
    pipeline.zremrangebyscore(key, 0, now - window)
    pipeline.zadd(key, {str(now): now})
    pipeline.zcount(key, now - window, now)
    pipeline.expire(key, window + 1)
    results = pipeline.execute()
    return results[2] <= limit
```

### Token Bucket (Lua)

Allows burst traffic with a steady refill rate.

```lua
-- Token bucket in Lua
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local tokens_per_second = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4] or 1)

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1] or capacity)
local last_refill = tonumber(bucket[2] or now)

-- Calculate tokens to add based on time elapsed
local elapsed = math.max(0, now - last_refill)
local tokens_to_add = elapsed * tokens_per_second
tokens = math.min(capacity, tokens + tokens_to_add)

if tokens >= requested then
    tokens = tokens - requested
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, capacity / tokens_per_second + 1)
    return 1
else
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, capacity / tokens_per_second + 1)
    return 0
end
```

---
[Back to Overview](./OVERVIEW.md)
