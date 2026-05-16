# Distributed Locking

### Simple Distributed Lock

Single-instance lock with TTL — prevents deadlocks if the holder crashes.

```python
import redis
import uuid
import time

class RedisLock:
    def __init__(self, redis_client, key, timeout=10):
        self.redis = redis_client
        self.key = key
        self.timeout = timeout
        self.identifier = str(uuid.uuid4())

    def acquire(self, blocking=True, timeout=None):
        end = time.time() + (timeout or self.timeout)
        while True:
            if self.redis.set(self.key, self.identifier, nx=True, ex=self.timeout):
                return True
            if not blocking or time.time() > end:
                return False
            time.sleep(0.001)

    def release(self):
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        return self.redis.eval(lua_script, 1, self.key, self.identifier)

    def extend(self, additional_time):
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("expire", KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        return self.redis.eval(lua_script, 1, self.key, self.identifier, self.timeout + additional_time)
```

### Redlock — Multiple Independent Instances

Distributed locking across multiple independent Redis instances:

1. Get current time in milliseconds.
2. Try to acquire lock in all N Redis instances sequentially.
3. Calculate elapsed time.
4. Lock acquired if **majority acquired AND `validity_time > 0`**.
5. If lock acquired, `validity_time = TTL - elapsed_time`.
6. If lock not acquired, release all instances.

```python
import redis
import time
import random

class Redlock:
    def __init__(self, redis_instances, resource, ttl=10000):
        self.instances = redis_instances
        self.resource = resource
        self.ttl = ttl
        self.quorum = len(redis_instances) // 2 + 1
        self.drift = int(ttl * 0.01) + 2

    def lock_instance(self, instance, value):
        try:
            return instance.set(self.resource, value, nx=True, px=self.ttl)
        except Exception:
            return False

    def unlock_instance(self, instance, value):
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        try:
            instance.eval(lua_script, 1, self.resource, value)
        except Exception:
            pass

    def acquire(self):
        value = f"{time.time()}:{random.random()}"
        start_time = int(time.time() * 1000)
        locked_instances = []
        for instance in self.instances:
            if self.lock_instance(instance, value):
                locked_instances.append(instance)
        elapsed_time = int(time.time() * 1000) - start_time
        validity_time = self.ttl - elapsed_time - self.drift
        if len(locked_instances) >= self.quorum and validity_time > 0:
            return value, validity_time
        else:
            for instance in self.instances:
                self.unlock_instance(instance, value)
            return None, 0

    def release(self, value):
        for instance in self.instances:
            self.unlock_instance(instance, value)
```

### Distributed Lock Safety Rules

- Always use a unique identifier for the lock value.
- Always set TTL to prevent deadlocks.
- Release **only if you own the lock** (check identifier).
- Use a Lua script for atomic check-and-delete.
- Consider clock drift in distributed environments.

---
[Back to Overview](./OVERVIEW.md)
