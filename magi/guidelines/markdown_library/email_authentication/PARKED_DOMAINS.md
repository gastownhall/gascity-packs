# Parked and Non-Sending Domain Protection

Domains that do not send email (parked domains, defensive registrations, legacy domains, redirect-only domains) are prime targets for spoofing because attackers know these domains are unlikely to be monitored. Comprehensive authentication records on non-sending domains are the cheapest and most effective anti-spoofing measure available.

### Required Record Set

Every non-sending domain publishes:

- **SPF**: `v=spf1 -all` (hardfail is correct here — no legitimate mail exists to protect).
- **DMARC**: `v=DMARC1; p=reject; rua=mailto:dmarc-agg@example.com` (reject everything, report everything).
- **DKIM** (optional): empty key to explicitly declare no signing key.
- **Null MX** (RFC 7505): `example.com. MX 0 .` (the dot indicates no mail server).

### Monitoring

Include parked domain DMARC reports in the same monitoring pipeline as active domains. Spoofing attempts against parked domains appear in aggregate reports. High volumes of failed authentication against a parked domain indicate active impersonation campaigns that may warrant additional defenses (takedown requests, brand protection services).

### Non-Sending Subdomains

Apply the same parked domain protection to subdomains that do not send email. The DMARC `sp=` tag covers unprotected subdomains, but explicit records on high-value subdomains (`mail.example.com`, `app.example.com`) provide defense-in-depth.

---
[Back to Overview](./OVERVIEW.md)
