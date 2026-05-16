# Upstream Resilience

```nginx
proxy_intercept_errors on;
proxy_next_upstream         error timeout http_502 http_503;
proxy_next_upstream_tries   2;
proxy_next_upstream_timeout 10s;

error_page 502 503 504 /maintenance.html;

location = /maintenance.html {
    root /var/www/maintenance;
    internal;
}
```

| Directive | Rule |
|:----------|:-----|
| `proxy_next_upstream` | `error timeout http_502 http_503` — exclude `http_404` and other application-level errors |
| `proxy_next_upstream_tries` | Finite (2–3); without a limit, NGINX retries across all upstreams, amplifying load |
| `proxy_intercept_errors on` | Enables NGINX to intercept upstream errors and serve custom error pages |
| `error_page` | Custom maintenance page for 502/503/504 |

---
[Back to Overview](./OVERVIEW.md)
