# App Configuration Fundamentals

### Service Purpose

Azure App Configuration provides centralized management of application settings and feature flags. It is **not** a secret store — it is a configuration store optimized for:

- Hierarchical key-value storage with labels for environment segregation
- Feature flag management with targeting and percentage rollouts
- Dynamic configuration refresh without application restart
- Point-in-time snapshots for configuration rollback
- Integration with Azure services and Kubernetes via providers

### Service Tier (Production)

Use the **Standard** tier for production workloads. Free tier lacks SLA, geo-replication, private endpoints, and sufficient request quotas.

Standard tier provides:
- 99.9% availability SLA
- 20,000 requests per hour (soft limit, increasable)
- Geo-replication for disaster recovery
- Private endpoint support
- Customer-managed encryption keys
- Soft delete with purge protection

### Key Naming Conventions

Keys follow a hierarchical namespace using **colons** as delimiters. Establish a consistent pattern:

```
{application}:{component}:{setting}
```

Examples:
- `OrderService:Database:ConnectionTimeout`
- `OrderService:Cache:ExpirationMinutes`
- `OrderService:Retry:MaxAttempts`
- `Shared:Logging:MinimumLevel`

Naming rules:
- **PascalCase for all segments**
- Maximum key length: 10,000 characters (practical limit: keep under 256)
- Avoid special characters except delimiters
- Prefix shared configuration with `Shared:` or equivalent
- Include application name to prevent collision in multi-tenant stores

Wrong: `OrderService.Database.ConnectionTimeout` (dots are not the delimiter).

### Labels for Environment Segregation

| Label | Purpose |
|:------|:--------|
| `Development` | Local development and feature branches |
| `Staging` | Pre-production validation |
| `Production` | Live workloads |
| (empty) | Default fallback when no label matches |

Applications request configuration with a specific label. The provider falls back to unlabeled values when labeled values don't exist. This enables environment-specific overrides while sharing common defaults.

### Content Types

| Content Type | Purpose |
|:-------------|:--------|
| `text/plain` | Simple string values (default) |
| `application/json` | Structured configuration objects |
| `application/vnd.microsoft.appconfig.keyvaultref+json;charset=utf-8` | Key Vault references |

JSON content type enables the SDK to deserialize complex configuration structures directly into application objects.

### Snapshots

Snapshots capture point-in-time configuration state for:
- Rollback after problematic configuration changes
- Audit compliance requiring historical configuration records
- Blue-green deployments requiring configuration parity verification

Create snapshots before significant configuration changes.

---
[Back to Overview](./OVERVIEW.md)
