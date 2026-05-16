# Lua Scripting

### Compare-and-Swap

Atomic compare-and-swap operation.

```lua
-- Compare and swap with validation
local current = redis.call('GET', KEYS[1])
if current == ARGV[1] then
    redis.call('SET', KEYS[1], ARGV[2])
    return 1
else
    return 0
end
```

### Sliding-Window Rate Limiter (Lua)

```lua
-- Rate limiting with sliding window
local key = KEYS[1]
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count < limit then
    redis.call('ZADD', key, now, now)
    redis.call('EXPIRE', key, window)
    return 1
else
    return 0
end
```

### Atomic Bulk Operation

```lua
-- Atomic multi-key update
local updates = 0
for i = 1, #KEYS do
    local result = redis.call('SET', KEYS[i], ARGV[i], 'EX', 3600)
    if result then updates = updates + 1 end
end
return updates
```

### Lua Script Constraints

- **Keep scripts short** — they block all other operations.
- All keys must be declared upfront in the `KEYS` array.
- In clusters, all keys must be on the same slot.
- Use **`EVALSHA`** to avoid sending script body repeatedly.
- `NOSCRIPT` fallback — if SHA not cached, send full script with `EVAL`.

---
[Back to Overview](./OVERVIEW.md)
