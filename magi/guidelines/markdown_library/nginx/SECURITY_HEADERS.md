# Security Headers

HTTP response headers instruct browsers to enforce security policies. **Missing headers leave clients vulnerable** to clickjacking, MIME sniffing, XSS, and protocol downgrade attacks. Apply security headers at the NGINX level for consistent enforcement across all upstream applications.

### Mandatory Headers

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=()" always;
add_header X-XSS-Protection "0" always;
server_tokens off;
```

| Header | Required Value | Purpose |
|:-------|:---------------|:--------|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` (after verifying all subdomains support HTTPS) | Prevents protocol downgrade |
| `X-Content-Type-Options` | `nosniff` | Prevents MIME-sniffing escalation |
| `X-Frame-Options` | `DENY` (or `SAMEORIGIN` if self-embedding) | Prevents clickjacking |
| `Referrer-Policy` | `strict-origin-when-cross-origin` or `no-referrer` | Limits referrer leakage |
| `Permissions-Policy` | Deny features the app does not use | Restricts browser feature surface |
| `X-XSS-Protection` | `0` | Disables flawed legacy XSS auditor |
| `server_tokens` | `off` | Removes NGINX version disclosure |

`X-Frame-Options: DENY` is preferred unless the site legitimately embeds its own pages in iframes. CSP `frame-ancestors` supersedes `X-Frame-Options` in modern browsers but include both for legacy coverage.

### Content Security Policy

Start with a restrictive baseline (`default-src 'self'`) and add exceptions for legitimate external resources. Deploy initially in **report-only mode** (`Content-Security-Policy-Report-Only`) to identify violations before enforcement.

### Cross-Origin Isolation

```nginx
add_header Cross-Origin-Opener-Policy "same-origin" always;
add_header Cross-Origin-Embedder-Policy "require-corp" always;
```

Set for pages needing process isolation (`SharedArrayBuffer`, high-resolution timers). **Omit** for pages embedding cross-origin iframes (Stripe Elements, YouTube) unless those resources send appropriate CORP/CORS headers.

---
[Back to Overview](./OVERVIEW.md)
