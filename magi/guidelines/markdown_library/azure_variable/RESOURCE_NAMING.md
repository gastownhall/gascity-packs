# Resource Naming Conventions

### General Format

```
{resource-type-abbr}-{application}-{environment}-{region}-{instance}
```

Maximum length 63 characters; charset alphanumeric + hyphen.

Example: `kv-orderservice-prod-eus-001`

### Resource-Type Abbreviations

| Resource | Abbr | Format | Example | Constraints |
|:---------|:-----|:-------|:--------|:------------|
| Key Vault | `kv` | `kv-{app}-{env}-{region}-{instance}` | `kv-orderservice-prod-eus-001` | ≤24 chars, alphanumeric, globally unique |
| App Configuration | `appcs` | `appcs-{app}-{env}-{region}` | `appcs-orderservice-prod-eus` | ≤50 chars, alphanumeric + hyphen |
| Storage Account | `st` | `st{app}{env}{region}{instance}` | `storderserviceprodeus001` | ≤24 chars, lowercase alphanumeric, globally unique |
| Cosmos DB | `cosmos` | `cosmos-{app}-{env}-{region}` | `cosmos-orderservice-prod-eus` | ≤44 chars, lowercase alphanumeric + hyphen |
| Azure SQL | `sql` | `sql-{app}-{env}-{region}` | `sql-orderservice-prod-eus` | ≤63 chars, lowercase alphanumeric + hyphen, globally unique |
| Service Bus | `sb` | `sb-{app}-{env}-{region}` | `sb-orderservice-prod-eus` | ≤50 chars, alphanumeric + hyphen, globally unique |
| Event Hub | `evh` | `evh-{app}-{env}-{region}` | `evh-orderservice-prod-eus` | ≤50 chars, alphanumeric + hyphen |
| Function App | `func` | `func-{app}-{env}-{region}` | `func-orderservice-prod-eus` | ≤60 chars, alphanumeric + hyphen, globally unique |
| App Service | `app` | `app-{app}-{env}-{region}` | `app-orderservice-prod-eus` | ≤60 chars, alphanumeric + hyphen, globally unique |
| Virtual Network | `vnet` | `vnet-{app}-{env}-{region}` | `vnet-orderservice-prod-eus` | ≤64 chars, alphanumeric + hyphen + underscore |
| Resource Group | `rg` | `rg-{app}-{env}-{region}` | `rg-orderservice-prod-eus` | ≤90 chars, alphanumeric + hyphen + underscore + period |
| Managed Identity | `id` | `id-{app}-{env}-{region}` | `id-orderservice-prod-eus` | ≤128 chars, alphanumeric + hyphen + underscore |

Storage Account is the exception that proves the rule: globally unique, lowercase, no separators. Compress the segments without delimiters.

---
[Back to Overview](./OVERVIEW.md)
