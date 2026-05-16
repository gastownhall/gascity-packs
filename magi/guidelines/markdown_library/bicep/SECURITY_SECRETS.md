# Security and Secrets Management

### Secret Parameters

Mark sensitive parameters with `@secure()`:

```bicep
@secure()
param sqlAdminPassword string

@secure()
param apiKey string
```

Secure parameters:
- Do not appear in deployment logs
- Are not stored in deployment history
- Must be provided at deployment time

### Key Vault Integration

Reference secrets from Key Vault in parameter files:

```json
{
  "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "sqlAdminPassword": {
      "reference": {
        "keyVault": {
          "id": "/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.KeyVault/vaults/{vault}"
        },
        "secretName": "sql-admin-password",
        "secretVersion": "optional-version-id"
      }
    }
  }
}
```

### Managed Identity

Prefer managed identity over connection strings:

```bicep
resource appService 'Microsoft.Web/sites@2023-01-01' = {
  name: appName
  identity: {
    type: 'SystemAssigned'
  }
  properties: { /* ... */ }
}

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, appService.id, storageBlobDataContributorRole)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: appService.identity.principalId
    principalType: 'ServicePrincipal'
  }
}
```

### Deployment Identity

- Scope permissions to target resource groups
- Use federated credentials for GitHub Actions and Azure DevOps
- Rotate credentials according to policy
- Audit deployment identity usage

### Network Security

Deploy resources with network restrictions by default:
- Deny public access where possible
- Use private endpoints for data services
- Restrict to VNet integration for compute
- **Wildcard `*` in IP rules or firewall configurations is forbidden**

---
[Back to Overview](./OVERVIEW.md)
