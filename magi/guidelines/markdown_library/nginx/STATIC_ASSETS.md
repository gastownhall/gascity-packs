# Static Asset Serving and Caching

Serve static assets directly without proxying — eliminates application server load for cacheable content.

### Cache Headers by Content Type

```nginx
# Versioned/fingerprinted assets — long cache + immutable
location ~* \.(css|js|woff2|jpg|jpeg|png|gif|svg)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
    try_files $uri =404;
}

# HTML — must always be fresh
location ~* \.html$ {
    add_header Cache-Control "no-cache, no-store, must-revalidate";
}
```

| Asset | Cache-Control |
|:------|:--------------|
| Versioned/fingerprinted | `public, immutable` + `expires 1y` |
| HTML | `no-cache, no-store, must-revalidate` (or short max-age + ETag) |

`immutable` prevents conditional requests for content that will never change at the same URL.

### try_files

```nginx
location / {
    try_files $uri $uri/ @backend;
}

location @backend {
    proxy_pass http://upstream;
}
```

Serves files directly from disk when they exist; proxies to the application only when they do not.

### Filesystem Tuning

```nginx
sendfile     on;
tcp_nopush   on;
tcp_nodelay  on;

open_file_cache          max=10000 inactive=60s;
open_file_cache_valid    120s;
open_file_cache_min_uses 2;
open_file_cache_errors   on;
```

`sendfile` offloads file reading to the kernel. `tcp_nopush` sends full packets. `tcp_nodelay` disables Nagle's algorithm for interactive connections. `open_file_cache` caches file descriptors and metadata, reducing filesystem syscalls per request.

---
[Back to Overview](./OVERVIEW.md)
