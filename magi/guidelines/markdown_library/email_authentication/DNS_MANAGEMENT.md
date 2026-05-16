# DNS Management for Email Records

Email authentication depends entirely on DNS. Incorrect, stale, or propagation-delayed DNS records cause immediate authentication failures.

### Validation

Validate DNS record syntax before publication. Use online validators (MXToolbox, dmarcian, URIports) to verify SPF, DKIM, and DMARC records are syntactically correct before publishing. A malformed record (missing semicolons, incorrect tag names, encoding errors) causes the entire record to be ignored or fail parsing.

### TTL Strategy

- Short TTLs (300–600s) during changes and migrations.
- Longer TTLs (3600–86400s) at steady state.
- Before making changes to email authentication records, reduce the TTL at least 24 hours in advance so the old, long TTL expires from caches before the change takes effect.

### Propagation Verification

Verify DNS propagation after every record change. Use tools that query multiple DNS resolvers worldwide (`whatsmydns.net`, `dig` against multiple resolvers). DMARC aggregate reports reflecting the old record indicate cached stale records. Wait for the old TTL to expire before assuming propagation is complete.

### Version Control

Version-control DNS zone files or use infrastructure-as-code (Terraform, Pulumi, OctoDNS) to manage email authentication DNS records. Manual changes in DNS provider web UIs are error-prone, unreviewable, and untraceable. DNS records are security-critical configuration that warrants the same change management rigor as application code.

### DNSSEC

Enable DNSSEC on all domains when the registrar and DNS provider support it. DNSSEC prevents DNS spoofing attacks that could redirect authentication record lookups to attacker-controlled responses. DNSSEC is a prerequisite for DANE (TLSA records) and strengthens the integrity of all DNS-based email authentication.

---
[Back to Overview](./OVERVIEW.md)
