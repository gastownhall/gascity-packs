# NGINX Configuration and Hardening Library

These guidelines define strict conventions for NGINX server block architecture, TLS hardening, reverse proxy configuration, security headers, rate limiting, performance tuning, logging, upstream resilience, and operational safety across all NGINX-fronted properties.

## Critical Mandates (Read First)
- **NGINX Is the Perimeter** — every security control enforceable at the edge MUST be enforced here.
- **Explicit Over Implicit** — every server/location block declares the directives it requires.
- **Deny by Default** — default catch-all returns 444; access to dotfiles and backups is denied.
- **Test Before Reload** — every config change passes `nginx -t` before reload.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [Server Block Architecture](./SERVER_BLOCKS.md)
3. [SSL/TLS Configuration](./SSL_TLS.md)
4. [Security Headers](./SECURITY_HEADERS.md)
5. [Reverse Proxy Configuration](./REVERSE_PROXY.md)
6. [Load Balancing](./LOAD_BALANCING.md)
7. [Rate Limiting](./RATE_LIMITING.md)
8. [Connection Limiting](./CONNECTION_LIMITING.md)
9. [Request Filtering and Access Control](./REQUEST_FILTERING.md)
10. [Compression](./COMPRESSION.md)
11. [Static Asset Serving and Caching](./STATIC_ASSETS.md)
12. [Logging and Observability](./LOGGING.md)
13. [Timeout and Connection Tuning](./TIMEOUTS.md)
14. [Worker Process Configuration](./WORKER_PROCESS.md)
15. [Buffer Configuration](./BUFFERS.md)
16. [FastCGI / PHP-FPM Integration](./FASTCGI.md)
17. [WebSocket Proxying](./WEBSOCKET.md)
18. [HTTP/2 and HTTP/3](./HTTP2_HTTP3.md)
19. [Content Security and MIME Handling](./MIME_HANDLING.md)
20. [Redirect and Rewrite Patterns](./REDIRECT_REWRITE.md)
21. [Health Check Endpoints](./HEALTH_CHECKS.md)
22. [Upstream Resilience](./UPSTREAM_RESILIENCE.md)
23. [File Upload Handling](./FILE_UPLOADS.md)
24. [DNS Resolution](./DNS_RESOLUTION.md)
25. [Configuration Management and Testing](./CONFIG_MANAGEMENT.md)
26. [Post-Reload Shakedown](./SHAKEDOWN.md)
27. [Monitoring and Metrics](./MONITORING.md)
28. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
29. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
30. [Required Practices](./REQUIRED_PRACTICES.md)
31. [Style Summary](./STYLE_SUMMARY.md)
