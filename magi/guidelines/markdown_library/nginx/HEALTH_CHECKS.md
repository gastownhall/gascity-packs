# Health Check Endpoints

```nginx
location = /health {
    access_log off;
    allow 10.0.0.0/8;
    allow 172.16.0.0/12;
    allow 192.168.0.0/16;
    deny  all;
    return 200 "ok\n";
    add_header Content-Type text/plain;
}

location = /ready {
    access_log off;
    allow 10.0.0.0/8;
    deny  all;
    proxy_pass http://upstream/health;
}
```

| Endpoint | Purpose |
|:---------|:--------|
| `/health` | Returns 200 directly from NGINX — verifies NGINX is running and accepting connections, independent of upstream health |
| `/ready` | Proxies to upstream's health check — verifies end-to-end connectivity. Use for Kubernetes readiness probes and load balancer health checks |

**Health endpoints should not be accessible from the public internet** — restrict to internal networks via `allow`/`deny`.

---
[Back to Overview](./OVERVIEW.md)
