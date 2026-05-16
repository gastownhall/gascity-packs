# DNS Resolution

NGINX resolves upstream hostnames at configuration load time by default and **caches the result permanently**. Dynamic upstreams (containers, cloud services) require explicit resolver configuration.

```nginx
resolver         127.0.0.1 valid=30s ipv6=off;
resolver_timeout 5s;

set $upstream "https://backend.example.com";
proxy_pass $upstream;
```

| Constraint | Rule |
|:-----------|:-----|
| Resolver required | When using hostnames in `proxy_pass` with a variable. Without it, variable-based `proxy_pass` fails entirely |
| `valid` parameter | DNS TTL |
| `ipv6=off` | Set unless IPv6 upstream connectivity is confirmed |
| Local resolver | Prefer over public DNS (8.8.8.8, 1.1.1.1) for lower latency and reduced external dependency |
| `resolver_timeout 5s` | Fail fast on DNS lookup failures |
| Static upstream blocks | Resolved once at startup — in Docker/Kubernetes where container IPs change, use the resolver directive with a `set` variable or service discovery |

---
[Back to Overview](./OVERVIEW.md)
