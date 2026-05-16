# Core Principles

These guidelines define strict, secure, and operationally sound patterns for domain management, DNS configuration, SSL/TLS, and CDN architecture, optimizing for:

- **DNS as Infrastructure**: DNS is the foundation of every web request. A misconfigured A record takes down a site faster than any application bug. Treat zone files with the same rigor as production code — version-controlled, reviewed, and tested before deployment.
- **Encryption Everywhere**: Every connection terminates with TLS. HTTP-only endpoints, self-signed certificates in production, and mixed content are security failures. Full-strict encryption from edge to origin is the only acceptable configuration.
- **Cache as Architecture**: CDN caching is not a performance afterthought bolted on later. Cache behavior is a first-class design decision that determines origin load, bandwidth cost, user experience, and invalidation complexity. Design for it from day one.
- **Registrar/DNS Separation**: The registrar holds the domain registration. The DNS provider serves authoritative responses. These can be the same vendor but are logically distinct services with different failure modes, different access controls, and different operational requirements.
- **Automate Certificate Lifecycle**: Manual certificate management is a ticking outage. Certificates expire. Renewal reminders get ignored. Staging certificates get deployed to production. Automate issuance, renewal, and deployment — then monitor the automation.
- **Control the Chain**: A domain resolves through a chain — registrar → nameservers → DNS records → CDN edge → origin. Every link is a potential failure point and a potential attack vector. Own every link. Document who controls each link. When an outage occurs at 2 AM, the on-call must know which vendor dashboard controls which piece — not discover it through trial and error.
- **Measure From Outside**: Internal monitoring tells you your servers are up. External DNS monitoring tells you your users can find your servers. These are different things. A healthy origin behind a broken DNS record serves zero requests. Monitor resolution time, propagation status, certificate expiry, and CDN cache hit ratios from external vantage points that mirror your users' perspective.

---
[Back to Overview](./OVERVIEW.md)
