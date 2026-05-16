# Naming Conventions

### Resource Naming

Azure resource names must be globally unique for some services, regionally unique for others, and subscription-unique for most. Establish a naming convention that encodes:

- **Workload/Application identifier**: What system does this resource belong to?
- **Environment**: dev, staging, prod
- **Region**: Abbreviated Azure region
- **Resource type**: Abbreviated resource type indicator
- **Instance**: Numeric or alphanumeric discriminator for multiple instances

Pattern: `{workload}-{environment}-{region}-{resourceType}-{instance}`

Examples:
- `orderapi-prod-eus2-app-001` (App Service)
- `orderapi-prod-eus2-sql-001` (SQL Server)
- `orderapiprodeus2st001` (Storage account — no hyphens allowed)

### Bicep Identifier Naming

| Element | Convention |
|:--------|:-----------|
| Parameters | `camelCase` with descriptive names: `storageAccountName`, `appServicePlanSku`, `enableDiagnostics` |
| Variables | `camelCase` describing the computed value: `resourceGroupLocation`, `formattedTags`, `subnetId` |
| Resources | `camelCase` symbolic name matching the resource purpose: `storageAccount`, `appServicePlan`, `sqlServer` |
| Modules | `camelCase` matching the module file name: `networking`, `database`, `monitoring` |
| Outputs | `camelCase` describing the exported value: `storageAccountId`, `primaryConnectionString`, `principalId` |

### Resource-Type Abbreviations

| Resource Type | Abbreviation |
|:--------------|:-------------|
| Resource Group | `rg` |
| Virtual Network | `vnet` |
| Subnet | `snet` |
| Network Security Group | `nsg` |
| App Service | `app` |
| App Service Plan | `asp` |
| Function App | `func` |
| Storage Account | `st` |
| Key Vault | `kv` |
| SQL Server | `sql` |
| Cosmos DB | `cosmos` |
| Container Registry | `acr` |
| Kubernetes Service | `aks` |

---
[Back to Overview](./OVERVIEW.md)
