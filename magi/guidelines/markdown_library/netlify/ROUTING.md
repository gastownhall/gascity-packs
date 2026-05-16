# Routing — Redirects and Rewrites

### Configuration Methods

Redirects and rewrites can be declared in `netlify.toml` (preferred) or a `_redirects` file in the publish directory. The `netlify.toml` format is more expressive: it supports conditions, header matching, country-based routing, and role-based access control.

| File | Processing | Format |
|:-----|:-----------|:-------|
| `_redirects` | Processed first | Simpler flat format for basic rules |
| `netlify.toml` | Processed second | Expressive, conditional, role-aware |

Within each file, rules evaluate **top-to-bottom**. The first matching rule wins. **Place specific rules before general ones.**

### Redirect vs Rewrite

| Type | Status | Behavior |
|:-----|:-------|:---------|
| Redirect | 301 / 302 | Browser URL changes |
| Rewrite | 200 | Serves content from a different path; URL unchanged |
| Proxy rewrite | 200 (external URL) | Forwards to upstream server; returns response transparently |

```toml
# Permanent redirect
[[redirects]]
  from = "/old-path"
  to = "/new-path"
  status = 301

# SPA fallback — rewrite all unmatched routes to index.html
[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200

# API proxy — forward to external backend
[[redirects]]
  from = "/api/*"
  to = "https://api.example.com/:splat"
  status = 200
  force = true
```

### SPA Routing

SPAs require a catch-all rewrite to serve `index.html` for all client-side routes. **Place this rule last** — it matches everything. Without `force = true`, the rule only applies when no file exists at the requested path. This is correct SPA behavior: serve the file if it exists, fall back to `index.html` otherwise.

### Proxy Rewrites

Proxy rewrites to external APIs hide the upstream URL from the browser, eliminating CORS issues for same-origin API calls and keeping backend URLs out of client code. Request flow: client → Netlify edge → upstream → Netlify edge → client.

Proxy rewrites add latency proportional to the distance between Netlify edge and upstream and count against bandwidth quotas. Use them for API gateway patterns, not for proxying large file downloads or streaming media.

### Trailing Slashes

Netlify applies Pretty URL normalization by default: `/about` serves `/about/index.html` if it exists. Configure trailing slash behavior explicitly if your framework has opinions. Inconsistent slash behavior between local and production causes routing bugs invisible until deploy.

---
[Back to Overview](./OVERVIEW.md)
