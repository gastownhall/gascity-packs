# Prohibited Practices

### Never Do

- Never leave auto-renewal disabled on production domains — a single missed renewal takes down everything: website, email, API, all services.
- Never use Cloudflare's Flexible SSL mode in production — encrypts only the client-to-edge leg; use Full (Strict) exclusively.
- Never expose origin server IPs in public DNS when using a CDN/reverse proxy — direct-to-origin connections bypass all CDN caching, WAF rules, and DDoS protection.
- Never manage DNS exclusively through a web dashboard — zone changes must be auditable; use API-driven management, IaC tools, or at minimum a change log documenting every modification.
- Never set TTL to 0 on production records — overloads authoritative servers, increases resolution latency, no operational benefit over 60s.
- Never skip DNSSEC validation testing after enabling or modifying DNSSEC — a broken chain of trust makes the domain unreachable for users behind validating resolvers.
- Never hardcode CDN edge IPs in application configuration — CDN IPs change; use CNAME or ALIAS records.
- Never deploy DMARC `p=reject` without a monitoring phase — legitimate senders that fail SPF/DKIM alignment will have their messages silently rejected.
- Never leave dangling CNAME records pointing to decommissioned services — they are subdomain takeover vulnerabilities.
- Never use wildcard DNS records (`*.example.com`) without understanding the implications — wildcards catch typos, attack probes, and subdomain enumeration; they can mask configuration errors and create unexpected routing.
- Never disable HTTPS or downgrade TLS versions to fix a certificate error — certificate errors indicate a configuration problem that must be resolved, not bypassed.
- Never share registrar account credentials across team members — use delegated access or API tokens with scoped permissions.

---
[Back to Overview](./OVERVIEW.md)
