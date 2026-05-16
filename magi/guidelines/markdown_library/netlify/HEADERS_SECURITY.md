# Custom Headers and Security

### Header Declaration

Declare custom headers in `netlify.toml` or a `_headers` file. **Headers apply only to static assets served by Netlify** — not to proxied content, function responses, or edge function responses. For dynamic responses, set headers in the function code directly.

```toml
[[headers]]
  for = "/*"
  [headers.values]
    X-Frame-Options = "DENY"
    X-Content-Type-Options = "nosniff"
    Referrer-Policy = "strict-origin-when-cross-origin"
    Permissions-Policy = "camera=(), microphone=(), geolocation=()"

[[headers]]
  for = "/assets/*"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"
```

### Security Headers Baseline

Every production site **must** include these headers. Non-negotiable for enterprise deployments.

| Header | Value | Purpose |
|:-------|:------|:--------|
| `X-Frame-Options` | `DENY` | Prevents clickjacking |
| `X-Content-Type-Options` | `nosniff` | Prevents MIME-type sniffing |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limits referrer leakage |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` (etc.) | Disables browser features the application does not use |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Enforces HTTPS — Netlify serves HTTPS by default; HSTS tells browsers to never downgrade |

Develop Content Security Policy in **report-only mode first**, then enforce. An overly restrictive CSP breaks functionality; an overly permissive one provides no protection.

### Basic Authentication

Netlify supports password protection via headers on Pro and Enterprise plans. Lightweight access control for staging or internal sites — **not a replacement for application-level authentication**. Basic auth credentials transmit base64-encoded (not encrypted); HTTPS is mandatory, which Netlify provides.

---
[Back to Overview](./OVERVIEW.md)
