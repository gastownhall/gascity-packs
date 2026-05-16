# Style Summary

| Element | Required Style |
|:--------|:---------------|
| **Architecture** | Default catch-all returns 444; one server block per service; modular includes; explicit directives over inheritance; deny by default |
| **TLS** | TLSv1.2 + TLSv1.3 only; strong ECDHE+AESGCM ciphers; full chain in cert; OCSP stapling; session cache; automated renewal with expiry alerting |
| **Security Headers** | HSTS 1yr with `includeSubDomains`; `nosniff`; `X-Frame-Options DENY/SAMEORIGIN`; strict `Referrer-Policy`; `Permissions-Policy`; CSP; `server_tokens off` |
| **Reverse Proxy** | `Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto` on every `proxy_pass`; HTTP/1.1 keepalive to upstream; bounded retries; proper redirect handling |
| **Load Balancing** | Algorithm matches use case; `max_fails`/`fail_timeout` tuned; `keepalive` to upstream pool; backup servers; active health checks where available |
| **Rate Limiting** | Per-IP zones on auth endpoints; `burst` with `nodelay`; 429 status; layered limits for APIs; monitored hit rates |
| **Access Control** | Block dotfiles, backups, config files; restrict HTTP methods; IP-restrict admin paths; explicit `client_max_body_size`; no PHP in uploads |
| **Compression** | `gzip on` with `gzip_proxied any`; text types only; Brotli alongside gzip; level 5–6 for CPU/ratio balance |
| **Static Assets** | Long cache for versioned assets; `no-cache` for HTML; `try_files` before proxy; `sendfile`+`tcp_nopush`; `open_file_cache` for high traffic |
| **Logging** | JSON structured format; `upstream_response_time` tracked; exclude health checks; warn level for production errors; never log credentials; rotate daily |
| **Timeouts** | `client_body`/`header_timeout` for slowloris; proxy connect/read/send per endpoint; `keepalive_timeout` balanced; extended timeouts for long-poll/SSE per location |
| **Workers** | `auto` `worker_processes`; 4096+ `worker_connections` for proxies; `epoll` + `multi_accept`; file descriptor limits match capacity |
| **FastCGI** | Unix sockets; `try_files $uri =404` before `fastcgi_pass`; block PHP in uploads; `fastcgi_cache` for cacheable responses |
| **WebSockets** | `Upgrade`/`Connection` headers; `proxy_read_timeout` matches heartbeat; `map` for conditional `Connection` |
| **HTTP/2/3** | `http2` on all HTTPS listeners; HTTP/3 via `quic reuseport` + `Alt-Svc`; `http2_max_concurrent_streams` capped |
| **Configuration** | Version-controlled; `nginx -t` gated; graceful reload; automated rollback; staging-tested before production |
| **Shakedown** | Real reload + listener binding + TLS chain + upstream probe + rate-limit firing + log writability; classify pass / fail-blocking / fail-nonblocking / inconclusive |
| **Monitoring** | `stub_status` on internal endpoint; alert on 5xx rate, latency, connection saturation, cert expiry; periodic TLS and header audits |
| **Defense in Depth** | `nginx -t` + active upstream health + multiple workers/instances + TLS renewal + rate limits + structured logs + canary reload |
| **Rule of Three** | `nginx -t` + active upstream health + production 5xx-rate alert MUST agree before declaring config push successful |

---
[Back to Overview](./OVERVIEW.md)
