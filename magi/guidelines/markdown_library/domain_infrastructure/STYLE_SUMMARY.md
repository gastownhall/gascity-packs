# Style Summary

| Element | Required Style |
|:--------|:---------------|
| Domain Registration | Auto-renewal enabled; registrar lock on; WHOIS privacy on; payment methods verified |
| Registrar vs DNS | Registration at registrar; authoritative DNS at best-fit provider; separate concerns |
| DNS Records | Lowercase names; descriptive subdomains; no orphaned records; quarterly audits |
| TTL Strategy | Stable records 1–24h; production records 5–60min; pre-change records 60–300s |
| DNSSEC | Enabled on all domains; Algorithm 13 preferred; DS records verified; automated key management |
| SSL/TLS | TLS 1.2 minimum; TLS 1.3 preferred; DV via ACME automation; HSTS on all production |
| Cloudflare SSL | Full (Strict) only; Origin CA or public cert on origin; authenticated origin pulls enabled |
| CAA Records | Published on every domain; restrict to authorized CAs; iodef contact configured |
| CDN Caching | Immutable assets: 1-year max-age; HTML: short max-age or must-revalidate; API: case-by-case |
| Cache Keys | Strip tracking params; sort query params; exclude cookies unless content varies per user |
| Cache Invalidation | Versioned filenames preferred; tag-based purge for content; never purge in request path |
| Origin Shielding | Enabled on paid CDN plans; shield PoP near origin; reduces origin load on cache miss |
| Cloudflare Proxy | Orange cloud for HTTP traffic; gray cloud for non-HTTP; origin IP hidden and firewalled |
| GoDaddy Usage | Registrar and portfolio management; external DNS for enterprise; Premium DNS if staying on GoDaddy NS |
| DNS Migration | Lower TTLs 48h before; recreate records before NS change; disable DNSSEC during migration |
| Email DNS | SPF with `-all`; DKIM per sending service; DMARC phased to `p=reject`; null MX for non-mail domains |
| Security | Origin IP hidden; registrar lock and 2FA; no dangling CNAMEs; DNS DDoS via anycast provider |
| Monitoring | External DNS resolution; cert expiry alerts; CDN hit ratio; synthetic HTTP probes multi-region |
| Shakedown | Run after every change to DNS / cert / CDN / origin; fixed URL corpus; multi-vantage; capture all artifacts |
| Defense in Depth | Multi-NS + DNSSEC + registrar locks + external monitoring + TTL discipline + versioned zones + cert monitoring |
| Rule of Three | At least three vantage points must agree before declaring a change live |

---

Following these rules produces domain infrastructure that is secure, resilient, performant, and operationally transparent. DNS stops being the thing that breaks at 2 AM because no one documented which dashboard controls it. Certificates stop expiring because automation handles renewal and monitoring catches failures. CDN caching stops being a guessing game because cache-control headers and invalidation strategies are designed, not discovered. Every domain in the portfolio has a known registrar, a known DNS provider, a known certificate authority, and a known person responsible for its lifecycle.

**Apply this guidance universally to all domains, DNS zones, certificates, and CDN configurations across the organization.**

---
[Back to Overview](./OVERVIEW.md)
