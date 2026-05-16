# Monitoring and Health Checks

### External DNS Monitoring

Monitor DNS resolution from external vantage points. Internal monitoring confirms your DNS servers respond; external monitoring confirms the global DNS system delivers correct answers to your users — these are different things.

Required:

- Resolution time — baseline and deviations.
- Record correctness — A record returns expected IP.
- DNSSEC validation status.
- Nameserver responsiveness.
- Propagation status after changes.

### Certificate Monitoring

Monitor certificate expiry for every production domain. Monitor CT logs for unauthorized certificate issuance — alert immediately when a certificate is issued by an unauthorized CA.

Required alerts:

- 30 days before expiration
- 14 days before expiration
- 7 days before expiration
- CT log monitoring for unauthorized issuance on all monitored domains

### CDN Cache Performance Monitoring

- Track **cache hit ratio** daily. A sudden drop indicates a configuration change, a deploy that broke cache headers, or a traffic pattern shift.
- Track **origin fetch volume** — a healthy CDN handles 80–95% of requests at the edge without touching the origin for cacheable content.
- Track **edge response time by region** to identify geographic performance issues.

### Uptime/Availability Monitoring

Synthetic monitoring (Pingdom, StatusCake, UptimeRobot, or equivalent) must probe production endpoints from multiple geographic locations at 1-minute intervals minimum. Check **full HTTP response** — not just TCP connectivity. A server returning 503 errors is up at the TCP level but down for users.

---
[Back to Overview](./OVERVIEW.md)
