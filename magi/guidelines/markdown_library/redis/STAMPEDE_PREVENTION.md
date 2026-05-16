# Cache Stampede Prevention

When a hot key expires, every concurrent request misses simultaneously and stampedes the data source.

### Probabilistic Early Expiration (XFetch)

Randomly refresh before actual expiration.

```python
import random
import time
import math

def get_with_xfetch(redis, key, fetch_func, ttl=3600, beta=1.0):
    """
    Probabilistic early expiration to prevent stampede.
    beta = 1.0 is optimal for most cases.
    """
    data = redis.get(key)
    if data:
        # Check if we should proactively refresh
        remaining_ttl = redis.ttl(key)
        if remaining_ttl > 0:
            # XFetch algorithm
            random_value = random.random()
            threshold = time.time() - (ttl - remaining_ttl) * beta * math.log(random_value)
            if time.time() >= threshold:
                # Refresh before expiration
                data = None
    if data is None:
        # Fetch and cache
        data = fetch_func()
        redis.set(key, data, ex=ttl)
    return data
```

### Lock-Based Regeneration

Single thread regenerates while others wait or use stale.

```python
def get_with_lock(redis, key, fetch_func, ttl=3600, lock_ttl=30):
    data = redis.get(key)
    if data is None:
        lock_key = f"{key}:lock"
        # Try to acquire regeneration lock
        if redis.set(lock_key, "1", nx=True, ex=lock_ttl):
            try:
                # We got the lock; regenerate
                data = fetch_func()
                redis.set(key, data, ex=ttl)
            finally:
                redis.delete(lock_key)
        else:
            # Another thread is regenerating
            # Option 1: Wait briefly and retry
            time.sleep(0.1)
            data = redis.get(key)
            # Option 2: Return stale data if available
            if data is None:
                stale_key = f"{key}:stale"
                data = redis.get(stale_key)
    return data
```

---
[Back to Overview](./OVERVIEW.md)
