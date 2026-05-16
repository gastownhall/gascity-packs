# Worker Process Configuration

```nginx
worker_processes  auto;
worker_rlimit_nofile 65535;

events {
    worker_connections 8192;
    use                epoll;
    multi_accept       on;
}
```

| Directive | Rule |
|:----------|:-----|
| `worker_processes auto` | Match number of CPU cores; manual values only when sharing host with CPU-intensive processes |
| `worker_connections` | ≥ 1024; 4096–8192 for high-traffic reverse proxies |
| Total capacity | `worker_processes × worker_connections`; each proxied connection consumes 2 (client-to-NGINX + NGINX-to-upstream) |
| `epoll` | Most efficient event model on Linux |
| `multi_accept on` | Workers accept multiple connections per event loop iteration |

Set the system-level file descriptor limit (`ulimit -n`) to **at least 2× `worker_connections`**. Configure in the NGINX systemd unit (`LimitNOFILE`) or `/etc/security/limits.conf`.

---
[Back to Overview](./OVERVIEW.md)
