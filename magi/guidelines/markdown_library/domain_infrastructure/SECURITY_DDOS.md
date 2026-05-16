# Security and DDoS Mitigation

### DNS-Layer DDoS Protection

DNS infrastructure is a primary target for DDoS attacks:

- **DNS amplification** — uses the domain's authoritative servers as an amplifier.
- **NXDomain attack** — floods the server with queries for nonexistent subdomains.

Mitigation: use an anycast DNS provider that absorbs volumetric attacks across a distributed network (Cloudflare, AWS Route53, Google Cloud DNS). Enable DNSSEC but be aware that DNSSEC increases response size — the anycast provider handles amplification risk at network scale.

### Origin IP Protection

When using a CDN or reverse proxy, the origin server's IP address must not be publicly resolvable:

- Restrict origin firewall rules to accept HTTP/HTTPS connections only from the CDN provider's IP ranges (Cloudflare publishes its IP ranges at `cloudflare.com/ips`).
- Check for origin IP leakage through:
  - Historical DNS records (SecurityTrails, DNS history databases)
  - Email headers (outbound email revealing the server IP)
  - Server-generated error pages
  - Direct IP scanning services (Censys, Shodan)

If the origin IP is exposed, the CDN/WAF layer can be bypassed entirely.

### Domain Hijacking Prevention

Domain hijacking occurs when an attacker gains control of the domain at the registrar level — redirecting nameservers, modifying records, or transferring the domain.

Required:

- Enable registrar lock on all domains.
- Enable two-factor authentication on all registrar accounts.
- Use a dedicated email address for domain registration that is not publicly associated with the organization.
- Enable registry lock for high-value domains.
- Restrict registrar account access to a minimum number of administrators.
- Monitor WHOIS/NS changes for critical domains using external monitoring tools.

### Subdomain Takeover

Subdomain takeover occurs when a DNS record (typically a CNAME) points to a service that the organization no longer controls. Example: `staging.example.com CNAME staging-app.herokuapp.com` — if the Heroku app is deleted, an attacker can claim that hostname on Heroku and serve content on `staging.example.com`.

Required:

- Remove DNS records when decommissioning services.
- Audit CNAME records quarterly for dangling references.
- Use automated scanning tools that check whether CNAME targets are claimable on known cloud platforms.

---
[Back to Overview](./OVERVIEW.md)
