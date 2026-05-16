# Domain Infrastructure Guidelines Library

This directory contains an expanded, modularized version of the Domain Infrastructure Guidelines. Apply universally to all domains, DNS zones, certificates, and CDN configurations across the organization.

## Critical Mandates (Read First)
- **DNS as Infrastructure** — treat zone files with the same rigor as production code; version-controlled, reviewed, tested.
- **Encryption Everywhere** — every connection terminates with TLS; Full-strict edge-to-origin only.
- **Automate Certificate Lifecycle** — manual cert management is a ticking outage.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md) — DNS as infrastructure, encryption, cache as architecture, registrar/DNS separation, lifecycle automation, control the chain, measure from outside.
2. [Domain Registration and Lifecycle](./DOMAIN_REGISTRATION.md) — Registrar selection, lifecycle, locking, WHOIS privacy, defensive registration.
3. [DNS Architecture and Record Types](./DNS_RECORDS.md) — A, AAAA, CNAME, ALIAS, MX, TXT, SRV, CAA, NS, naming conventions.
4. [DNS Zone Management](./DNS_ZONE_MANAGEMENT.md) — Authoritative DNS, zone discipline, orphaned audits, secondary DNS.
5. [TTL Strategy](./TTL_STRATEGY.md) — Fundamentals, by record type, anti-patterns.
6. [DNSSEC](./DNSSEC.md) — Purpose, key types, algorithm selection, enabling, key rollover.
7. [SSL/TLS Certificate Management](./CERT_MANAGEMENT.md) — Types, automation, CAA, wildcards, CT.
8. [SSL/TLS Configuration and Hardening](./TLS_HARDENING.md) — Min TLS, ciphers, HSTS, Cloudflare SSL modes, origin certs, authenticated pulls.
9. [CDN Architecture and Caching](./CDN_CACHING.md) — Fundamentals, Cache-Control, cache key, origin shielding, content-type caching.
10. [CDN Cache Invalidation](./CDN_INVALIDATION.md) — Methods, design principles.
11. [Cloudflare-Specific Configuration](./CLOUDFLARE_CONFIG.md) — Proxy mode, rules, WAF, DNS features.
12. [GoDaddy-Specific Configuration](./GODADDY_CONFIG.md) — DNS management, Premium DNS, transfers, registrar with external DNS.
13. [DNS Migration and Cutover](./DNS_MIGRATION.md) — Pre-migration checklist, execution, cutover risks.
14. [Email DNS Records](./EMAIL_DNS.md) — SPF, DKIM, DMARC, null MX.
15. [Security and DDoS Mitigation](./SECURITY_DDOS.md) — DNS-layer DDoS, origin IP protection, hijacking, subdomain takeover.
16. [Monitoring and Health Checks](./MONITORING.md) — External DNS, certificate, CDN cache, uptime.
17. [Shakedown — Post-Change Integration Validation](./SHAKEDOWN.md) — Definition, triggers, validation categories, execution, classification, anti-patterns.
18. [Defense in Depth](./DEFENSE_IN_DEPTH.md) — Independent layers, Rule of Three.
19. [Prohibited Practices](./PROHIBITED_PRACTICES.md) — Never Do list.
20. [Required Practices](./REQUIRED_PRACTICES.md) — Always Do list.
21. [Style Summary](./STYLE_SUMMARY.md) — Quick-reference table for required styles.
