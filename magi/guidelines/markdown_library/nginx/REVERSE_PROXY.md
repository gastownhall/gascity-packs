# Reverse Proxy Configuration

NGINX as a reverse proxy terminates client connections, enforces security policy, and forwards requests to upstream application servers. **Proxy configuration must preserve client context, prevent header injection, and maintain connection efficiency.**

### Required Proxy Headers

```nginx
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

| Header | Purpose |
|:-------|:--------|
| `Host` | Original Host — without it, virtual host routing, absolute URL generation, and cookie domain matching break |
| `X-Real-IP` | Direct client IP |
| `X-Forwarded-For` | Forwarding chain |
| `X-Forwarded-Proto` | Original scheme — applications use this for secure cookie flags, HSTS, redirect URL generation |

### HTTP/1.1 Keepalive to Upstream

```nginx
proxy_http_version 1.1;
proxy_set_header Connection "";
```

Empty `Connection` header prevents forwarding the client's `Connection: close` to the upstream and enables keepalive.

### Redirect Handling

```nginx
proxy_redirect off;          # or `proxy_redirect default` — never leave to chance
```

Mismatched `proxy_redirect` causes redirect loops or exposes internal hostnames/ports in `Location` headers visible to clients.

### Header Hygiene

Clear or explicitly set `proxy_set_header` for headers the upstream should not receive from untrusted clients. Specifically clear `X-Forwarded-Host`, `X-Forwarded-Port`, and any custom headers your application trusts, then set them from NGINX variables. **This prevents header injection where a client sends a spoofed `X-Forwarded-For`.**

### Upstream Retries

```nginx
proxy_next_upstream         error timeout http_502 http_503;
proxy_next_upstream_tries   3;
proxy_next_upstream_timeout 10s;
```

Do not retry on POST/PUT/DELETE by default unless the upstream guarantees idempotency.

---
[Back to Overview](./OVERVIEW.md)
