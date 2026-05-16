# Compression

### gzip

```nginx
gzip               on;
gzip_vary          on;
gzip_proxied       any;
gzip_comp_level    5;
gzip_min_length    256;
gzip_types         text/plain text/css text/xml text/javascript
                   application/json application/javascript application/xml
                   application/xml+rss application/wasm image/svg+xml;
```

Level 5 provides a good compression/CPU tradeoff. Levels above 6 yield diminishing returns with increasing CPU cost. **Do not compress already-compressed formats** (images, video, fonts with WOFF2).

`gzip_proxied any` is mandatory — the default (`off`) disables compression for proxied responses, which is the majority of traffic in reverse proxy configurations.

### Brotli

```nginx
brotli             on;
brotli_comp_level  6;
brotli_types       text/plain text/css text/xml text/javascript
                   application/json application/javascript application/xml
                   application/xml+rss application/wasm image/svg+xml;
```

Brotli (via `ngx_brotli` module) achieves 15–25% better compression than gzip on text content. Browsers negotiate compression via `Accept-Encoding`.

---
[Back to Overview](./OVERVIEW.md)
