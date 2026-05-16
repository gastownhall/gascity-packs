# Required Practices

### Always Do

- Always enable auto-renewal and verify payment methods on all production domains.
- Always use Full (Strict) SSL mode when proxying through Cloudflare.
- Always publish CAA records restricting certificate issuance to authorized CAs.
- Always enable DNSSEC on all domains and verify the chain of trust.
- Always set security headers (HSTS, `X-Frame-Options`, `X-Content-Type-Options`) on all production endpoints.
- Always lower TTLs before planned DNS changes and raise them after verification.
- Always maintain a domain inventory with registration dates, expiry dates, registrar, DNS provider, and responsible team.
- Always configure SPF, DKIM, and DMARC for every domain that sends email.
- Always restrict origin server access to CDN IP ranges when using a reverse proxy.
- Always monitor DNS resolution, certificate expiry, and CDN cache performance from external vantage points.
- Always audit zone files quarterly for orphaned records and dangling CNAMEs.
- Always use content-hashed filenames for static assets to eliminate cache invalidation complexity.
- Always run a post-change shakedown after any change to DNS, certificates, CDN rules, or origin routing.

---
[Back to Overview](./OVERVIEW.md)
