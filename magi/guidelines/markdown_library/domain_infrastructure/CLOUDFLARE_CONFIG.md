# Cloudflare-Specific Configuration

### Cloudflare Proxy Mode

Cloudflare DNS records have two modes:

| Mode | Behavior |
|:-----|:---------|
| Proxied (orange cloud) | Routes traffic through Cloudflare's edge; enables CDN caching, DDoS protection, WAF, SSL termination, all Cloudflare features |
| DNS-only (gray cloud) | Resolves to the origin IP directly |

Required:

- **Proxy** all records that serve HTTP/HTTPS traffic.
- **DNS-only** for MX records, records pointing to non-HTTP services (databases, SSH, game servers), and records where revealing the origin IP is acceptable and proxy features are unnecessary.

Proxied records hide the origin IP from public DNS resolution. However, the origin IP can still leak through email headers, server-generated URLs, and historical DNS records. Pair Cloudflare proxy with origin firewall rules that restrict HTTP access to Cloudflare IP ranges only.

### Cloudflare Rules

Cloudflare provides layered rule systems for controlling traffic behavior. For new configurations:

- **Cache Rules (modern)** — granular caching control with flexible matching conditions; preferred for all new cache configuration.
- **Configuration Rules** — override SSL, minification, and other settings per URL pattern.

Forbidden:

- **Page Rules (legacy)** for new configuration — limited quantity (3 on free, 20–125 on paid) and less flexible matching syntax.

### Cloudflare WAF

Cloudflare's Web Application Firewall operates in front of the origin.

- Enable managed rules on all production domains.
- Review WAF event logs weekly during initial deployment to identify false positives.
- Tune rules by creating exceptions for legitimate traffic patterns before disabling entire rule categories.
- Rate-limiting rules protect API endpoints and login pages from brute-force attacks. Configure based on request path, HTTP method, and client characteristics; start permissive and tighten based on observed patterns.
- Bot management distinguishes automated traffic from human visitors on paid plans. Configure bot scoring to block malicious bots while permitting legitimate crawlers (Googlebot, Bingbot).

### Cloudflare DNS Features

- **CNAME Flattening** — automatically resolves CNAME records at the zone apex by returning A/AAAA records to resolvers; enables apex domains to point to CDN, load balancer, or PaaS hostnames; enabled by default on all Cloudflare zones.
- **Orange-to-Orange (O2O)** — when Cloudflare proxies a record pointing to another Cloudflare-proxied hostname, both layers of protection apply. Be aware this stacking can cause unexpected behavior with SSL modes and caching; test thoroughly.

---
[Back to Overview](./OVERVIEW.md)
