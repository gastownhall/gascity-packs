# Rate Limiting

Protects upstream services from traffic spikes, brute-force attacks, credential stuffing, and abusive clients. NGINX's `limit_req` module provides token-bucket rate limiting.

### Zone Definition

```nginx
http {
    limit_req_zone $binary_remote_addr zone=general:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=login_strict:10m rate=5r/m;
}
```

Key by `$binary_remote_addr` for per-IP limiting. Size the shared memory zone for the expected number of concurrent client IPs.

### Apply With Burst and Status

```nginx
location /api/ {
    limit_req         zone=general burst=20 nodelay;
    limit_req_status  429;
    limit_req_log_level warn;
}

location = /login {
    limit_req         zone=login_strict burst=5 nodelay;
    limit_req_status  429;
}
```

| Directive | Purpose |
|:----------|:--------|
| `burst` | Allows temporary spikes up to the specified number of requests |
| `nodelay` | Processes burst requests immediately rather than queuing |
| `limit_req_status 429` | HTTP 429 Too Many Requests — default 503 misleads monitoring and triggers inappropriate retries |
| `limit_req_log_level warn` | Logs rate-limited requests at warn level |

### Authentication Endpoints

Apply strict limits (`rate=5r/m` or lower) to login, password reset, and token exchange. Credential stuffing and brute-force attacks target these specifically.

### API Gateway Layering

Layer rate limits: a global per-IP limit and a per-endpoint limit on expensive operations. Use `map` directives to vary the rate limit key by API key or authenticated user when available.

---
[Back to Overview](./OVERVIEW.md)
