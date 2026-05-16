# Security Practices

### Authentication

| Method | Use case |
|:-------|:---------|
| Primary/Secondary Keys | Admin only; full access. Never expose to client applications. |
| Resource Tokens | Scoped, short-lived; for client applications. |
| Azure AD Authentication | Service-to-service; recommended. |
| **Managed Identity** | Azure-hosted services; no credentials in code. |

### Role-Based Access Control

Built-in data plane roles:

| Role | Permissions |
|:-----|:------------|
| Cosmos DB Built-in Data Reader | Read operations only |
| Cosmos DB Built-in Data Contributor | Read and write operations |
| Cosmos DB Built-in Data Owner | Full access including throughput and policy changes |

**Assign least-privilege roles.** Applications rarely need Owner role.

### Network Security

| Option | Priority |
|:-------|:---------|
| Private endpoints | Highest — Cosmos DB accessible only from VNet; no public exposure |
| IP firewall | Medium — restrict to known IP ranges when private endpoint not feasible |
| VNet service endpoints | Low — simpler but less isolated |

### Encryption

| Layer | Requirement |
|:------|:------------|
| At rest | Default with Microsoft-managed keys; customer-managed keys (CMK) available |
| In transit | TLS 1.2 enforced |
| Client-side | Recommended for sensitive fields (defense in depth) |

### Key Rotation

- Rotate primary/secondary keys periodically
- Regenerate without downtime: use secondary, regenerate primary, switch to primary, regenerate secondary
- **Managed identity eliminates key rotation concerns**

---
[Back to Overview](./OVERVIEW.md)
