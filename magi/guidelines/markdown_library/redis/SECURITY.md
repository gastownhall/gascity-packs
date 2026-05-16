# Security Practices

### Authentication

| Method | Notes |
|:-------|:------|
| Access keys | Azure Cache provides primary and secondary keys; rotate periodically; secondary key enables rotation without downtime |
| Azure AD authentication (Preview) | Token-based with Azure AD principals; fine-grained RBAC; no static keys |

**Never embed keys in source code** — use secret management.

### Encryption

| Layer | Configuration |
|:------|:--------------|
| In-transit | TLS required for Azure Cache for Redis; port 6380 (TLS) vs 6379 (non-TLS, disabled by default in Azure); minimum TLS 1.2 |
| At-rest | Premium and Enterprise tiers encrypt data at rest; Microsoft-managed keys by default; customer-managed keys (CMK) available |

### Network Security

- **Firewall rules** — restrict access by IP range; whitelist application IPs only; **never allow `0.0.0.0/0`** in production.
- **VNet integration (Premium+)** — cache deployed in customer VNet; no public IP; requires dedicated subnet.
- **Private endpoint** — Private Link for secure connectivity from VNets; traffic stays on Azure backbone; recommended for production.

### Least Privilege Access

- Separate accounts (different access keys or Azure AD principals per application).
- Read-only access where supported.
- Disable dangerous commands (`CONFIG`, `FLUSHALL`, `DEBUG`) via Redis configuration.

---
[Back to Overview](./OVERVIEW.md)
