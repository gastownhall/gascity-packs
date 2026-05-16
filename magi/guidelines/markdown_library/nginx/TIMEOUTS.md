# Timeout and Connection Tuning

| Directive | Typical Value | Purpose |
|:----------|:--------------|:--------|
| `client_body_timeout` | 10–30s | Slowloris mitigation — close clients sending body data too slowly |
| `client_header_timeout` | 10–30s | Slowloris mitigation — close clients sending headers too slowly |
| `proxy_connect_timeout` | 5–10s | Time to establish upstream connection |
| `proxy_read_timeout` | Per endpoint | Time to wait for upstream response (300–3600s for long-poll/SSE per location) |
| `proxy_send_timeout` | Per endpoint | Time to transmit request to upstream |
| `keepalive_timeout` | 65s | Balance connection reuse and resource consumption |
| `send_timeout` | 30–60s | Timeout for transmitting response to client |

Set tighter timeouts for API endpoints than for report generation or file upload endpoints. **Per-location timeout overrides prevent global timeout relaxation.**

---
[Back to Overview](./OVERVIEW.md)
