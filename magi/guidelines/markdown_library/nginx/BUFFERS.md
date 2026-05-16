# Buffer Configuration

Undersized buffers force disk I/O. Oversized buffers waste memory and enable memory exhaustion attacks.

```nginx
proxy_buffer_size            8k;
proxy_buffers                8 16k;
proxy_busy_buffers_size      32k;
client_body_buffer_size      16k;
large_client_header_buffers  4 16k;
```

| Directive | Purpose |
|:----------|:--------|
| `proxy_buffer_size` | Upstream response headers (typically 4k–8k; 16k for apps with large cookies/auth tokens). Undersized causes 502 |
| `proxy_buffers` | Response body buffering. For streaming/large endpoints, use `proxy_buffering off` |
| `client_body_buffer_size` | Typical request body sizes; bodies exceeding this spill to `client_body_temp_path` |
| `large_client_header_buffers` | Large cookies, long URLs, complex query strings. Default (4 8k) rejects requests >8k per buffer |

---
[Back to Overview](./OVERVIEW.md)
