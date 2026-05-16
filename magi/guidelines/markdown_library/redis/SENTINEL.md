# Redis Sentinel (Self-Managed)

> **Note:** Azure Cache for Redis handles failover automatically. Sentinel is for self-managed Redis only.

### Sentinel Configuration

```text
# sentinel.conf
port 26379
dir /tmp

# Monitor master
sentinel monitor mymaster redis-master.example.com 6379 2
sentinel auth-pass mymaster MyRedisPassword
sentinel down-after-milliseconds mymaster 30000
sentinel parallel-syncs mymaster 1
sentinel failover-timeout mymaster 180000

# Notification scripts
sentinel notification-script mymaster /usr/local/bin/notify.sh
sentinel client-reconfig-script mymaster /usr/local/bin/reconfig.sh

# Security
requirepass SentinelPassword
protected-mode yes
bind 127.0.0.1 ::1

# Logging
logfile /var/log/redis/sentinel.log
loglevel notice
```

### Deployment Requirements

- **Minimum 3 Sentinel instances** for quorum.
- Sentinels on separate hosts from Redis instances.
- **Odd number** of Sentinels to avoid split-brain.

### Sentinel-Aware Client (Python)

```python
from redis.sentinel import Sentinel

# Connect to Sentinel instances
sentinel = Sentinel([
    ('sentinel1.example.com', 26379),
    ('sentinel2.example.com', 26379),
    ('sentinel3.example.com', 26379)
], sentinel_kwargs={'password': 'SentinelPassword'})

# Discover master and replica addresses
master = sentinel.master_for('mymaster', socket_timeout=0.1, password='MyRedisPassword')
replica = sentinel.slave_for('mymaster', socket_timeout=0.1, password='MyRedisPassword')

# Use master for writes
master.set('key', 'value')

# Use replica for reads (optional)
value = replica.get('key')
```

### Sentinel Best Practices

- Use at least 3 Sentinel instances.
- Configure quorum as majority (`n/2 + 1`).
- Place Sentinels in different failure zones.
- Monitor Sentinel logs for failover events.
- Test failover scenarios regularly.

---
[Back to Overview](./OVERVIEW.md)
