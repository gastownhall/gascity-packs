# DNS Zone Management

### Authoritative DNS Selection

The authoritative DNS provider serves responses to resolvers worldwide. For organizations using Cloudflare as CDN, using Cloudflare DNS eliminates the proxy/DNS-provider coordination that causes configuration errors. For domains registered at GoDaddy but requiring enterprise DNS performance, point nameservers to Cloudflare or another enterprise DNS provider while keeping registration at GoDaddy.

Required capabilities:

- Global anycast network presence — more PoPs equals lower resolution latency
- Query-per-second capacity sufficient for traffic volume
- DNSSEC signing support
- API for programmatic zone management
- Secondary DNS support for redundancy
- Uptime SLA

### Zone File Discipline

Treat zone files as infrastructure code. Every record addition, modification, or deletion must be documented with purpose, requester, and date. For organizations managing zones via API, maintain a Terraform, Pulumi, or custom IaC configuration that represents the desired zone state and reconciles drift.

### Orphaned Record Audits

Orphaned records accumulate over time:

- A records pointing to decommissioned servers
- CNAME records targeting services that no longer exist
- TXT records for verification challenges completed years ago

Dangling DNS records pointing to unclaimed cloud resources enable subdomain takeover attacks. Audit zone files quarterly. Remove records that serve no current purpose.

### Secondary DNS

For critical domains, configure secondary DNS with a different provider. If the primary DNS provider experiences an outage, secondary nameservers continue serving responses. The primary provider pushes zone updates to the secondary via AXFR/IXFR zone transfers or API synchronization. Both primary and secondary nameservers must be listed in the domain's NS records at the registrar. Secondary DNS is insurance — the cost is negligible compared to the cost of a DNS outage.

---
[Back to Overview](./OVERVIEW.md)
