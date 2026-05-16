# HTTP/2 and HTTP/3

```nginx
listen 443 ssl http2;
listen [::]:443 ssl http2;
listen 443 quic reuseport;
listen [::]:443 quic reuseport;

add_header Alt-Svc 'h3=":443"; ma=86400';

http2_max_concurrent_streams 128;
```

| Protocol | Notes |
|:---------|:------|
| HTTP/2 | Enable on all HTTPS listeners. Multiplexes requests over a single TCP connection — no application changes required |
| HTTP/3 (QUIC) | NGINX 1.25.1+; uses UDP, eliminates TCP head-of-line blocking. Requires OpenSSL 3.x or BoringSSL with QUIC support |
| `http2_max_concurrent_streams` | 128–256 typical; very high values let a single client monopolize resources |

---
[Back to Overview](./OVERVIEW.md)
