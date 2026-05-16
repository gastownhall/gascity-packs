# Load Balancing

NGINX distributes traffic across upstream pools. Strategy, health checking, and failover configuration determine availability under load and during partial outages.

### Algorithm Selection

| Algorithm | Use For |
|:----------|:--------|
| `least_conn` | Heterogeneous backends with varying response times |
| `ip_hash` / `hash $request_uri consistent` | Session affinity when required |
| Round-robin (default) | Homogeneous backends with stateless apps |

### Upstream Block

```nginx
upstream backend {
    least_conn;
    keepalive 32;
    server backend1.example.com:8080 max_fails=3 fail_timeout=30s;
    server backend2.example.com:8080 max_fails=3 fail_timeout=30s;
    server backend3.example.com:8080 backup;
    server backend4.example.com:8080 down;   # explicitly removed
}
```

| Constraint | Rule |
|:-----------|:-----|
| `max_fails` / `fail_timeout` | Tune based on the upstream's actual failure characteristics; defaults (`max_fails=1, fail_timeout=10s`) are often too aggressive |
| `keepalive` | 32 typical; adjust per traffic; requires `proxy_http_version 1.1` and empty `Connection` header |
| `backup` | Receives traffic only when all primary servers unavailable |
| `down` | Server temporarily removed from rotation without deleting config |

### Active Health Checks

Open-source NGINX supports only **passive** health checks (monitoring actual request failures). For NGINX Plus or third-party modules, enable active checks against a dedicated health endpoint on the upstream.

---
[Back to Overview](./OVERVIEW.md)
