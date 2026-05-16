# DNS Architecture and Record Types

### A Record

Maps a hostname to an IPv4 address. The root record (`@`) points the bare domain to a server. Use for apex domains that cannot use CNAME per RFC 1034. Multiple A records for the same hostname enable basic round-robin load distribution.

### AAAA Record

Maps a hostname to an IPv6 address. Deploy AAAA records alongside A records for dual-stack resolution. IPv6-only clients cannot reach IPv4-only endpoints. The percentage of IPv6 traffic is significant and growing — ignoring it silently excludes users.

### CNAME Record

Maps a hostname to another hostname (canonical name). Cannot coexist with other record types at the same name. Cannot be used at the zone apex per the DNS specification. When a CDN or hosting provider gives you a CNAME target, use it on subdomains. For apex domains, use the provider's ALIAS/ANAME/flattened CNAME equivalent if available.

### ALIAS / ANAME Record

A provider-specific extension that resolves a CNAME-like record at the zone apex by performing resolution at the authoritative server level and returning an A/AAAA record to the querying resolver. Cloudflare calls this CNAME flattening. Not all DNS providers support this. If your provider does not, you must use A records for the apex and manage IP changes manually or via API.

### MX Record

Routes email for the domain to mail servers. Priority values determine preference order (lower number = higher priority). Every domain that sends or receives email must have MX records. Domains that do not handle email must still have a null MX record (`0 .`) to explicitly signal non-participation, reducing backscatter from spoofed messages.

### TXT Record

Stores arbitrary text. Used for domain verification, SPF email authentication, DMARC policies, DKIM public keys, and custom application metadata. TXT records have a 255-character per string limit, but multiple strings concatenate within a single record. Long values (common with DKIM keys) require proper string splitting.

### SRV Record

Specifies the location of services with protocol, port, priority, and weight. Used for SIP, XMPP, LDAP, and other service discovery protocols.

Format:
```text
_service._protocol.name TTL IN SRV priority weight port target
```

### CAA Record

Certificate Authority Authorization restricts which CAs can issue certificates for the domain. CAA records are checked by compliant CAs before issuance — a defense-in-depth control against misissued certificates. Add `iodef` to receive violation notifications.

```dns
0 issue "letsencrypt.org"
0 iodef "mailto:security@example.com"
```

### NS Record

Delegates authority for a zone or subdomain to specific nameservers. NS records at the zone apex define authoritative nameservers for the entire domain. NS records for subdomains delegate that subtree to different nameservers (subdomain delegation).

### Record Naming Conventions

Use lowercase for all DNS record names. DNS is case-insensitive per specification, but consistent lowercase avoids confusion in zone files and API integrations. Use descriptive subdomain names that convey purpose. Avoid generic names like `server1` or `test` — they convey nothing about the record's role.

Required examples:
- `api.example.com` — API endpoints
- `staging.example.com` — staging environments
- `mail.example.com` — mail services

---
[Back to Overview](./OVERVIEW.md)
