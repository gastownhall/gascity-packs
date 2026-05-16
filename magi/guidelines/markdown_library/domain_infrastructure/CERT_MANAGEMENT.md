# SSL/TLS Certificate Management

### Certificate Types

| Type | Use Case |
|:-----|:---------|
| Domain Validated (DV) | Proves control of the domain; issued in seconds to minutes; sufficient for the majority of web applications. Let's Encrypt, Cloudflare, and most CDN providers issue DV automatically and for free. |
| Organization Validated (OV) | Adds verified organization name; browsers do not visually distinguish OV from DV. |
| Extended Validation (EV) | Adds legal existence verification; most browsers have removed the visual EV indicator. Use only when regulatory or contractual requirements mandate it. |

### Certificate Automation

Automate certificate issuance, renewal, and deployment using **ACME (Automated Certificate Management Environment)**. Let's Encrypt is the most widely deployed ACME CA. Certbot, acme.sh, and Caddy are battle-tested ACME clients.

- Certificates have 90-day lifetimes by default.
- Renewal must trigger at least 30 days before expiration.
- Monitor for renewal failures and alert if a certificate is within 14 days of expiry without a successful renewal.
- Certificate monitoring must be **independent** of the renewal system to catch failures in the automation itself.

### CAA Records

Publish CAA records for every domain to restrict which CAs can issue certificates. Without CAA records, any CA can issue a certificate for your domain if they validate domain control.

```dns
example.com.  IN  CAA  0 issue "letsencrypt.org"
example.com.  IN  CAA  0 issue "digicert.com"
example.com.  IN  CAA  0 issuewild "letsencrypt.org"
example.com.  IN  CAA  0 iodef "mailto:security@example.com"
```

If only `issue` is present without `issuewild`, the issue restriction applies to wildcard issuance as well.

### Wildcard Certificates

Wildcard certificates (`*.example.com`) cover all single-level subdomains. They do **not** cover the apex (`example.com`) or multi-level subdomains (`sub.sub.example.com`). Use wildcards to reduce certificate management overhead when operating many subdomains. Do not use wildcards as a substitute for understanding which subdomains exist — inventory your subdomains independently of certificate coverage.

### Certificate Transparency (CT)

All publicly trusted CAs must log certificates to Certificate Transparency logs. Monitor CT logs for unauthorized certificate issuance on your domains. Services like `crt.sh`, Facebook CT monitoring, and Cloudflare's CT alerting provide notifications when certificates are issued for monitored domains. An unexpected certificate issuance indicates either a CA compromise, a domain validation bypass, or unauthorized access to your DNS — all of which require immediate investigation.

---
[Back to Overview](./OVERVIEW.md)
