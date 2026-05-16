# Deployment Scopes

### Scope Hierarchy

| Scope | Description |
|:------|:------------|
| Resource group | Default scope; most resource deployments |
| Subscription | Resource groups, policies, role assignments |
| Management group | Policies, blueprints across subscriptions |
| Tenant | Management groups, tenant-level configurations |

### Targeting Scopes

```bicep
targetScope = 'subscription'

param rgName string
param location string

resource resourceGroup 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: rgName
  location: location
  tags: {
    Environment: 'Production'
    ManagedBy: 'Bicep'
  }
}

module infrastructure 'main.bicep' = {
  name: 'infrastructure'
  scope: resourceGroup
  params: {
    location: location
  }
}

// Cross-subscription deployment
module crossSubResources 'modules/shared.bicep' = {
  name: 'shared-resources'
  scope: resourceGroup(otherSubscriptionId, sharedResourceGroupName)
  params: { /* ... */ }
}
```

### Cross-Scope References

```bicep
resource crossSubRg 'Microsoft.Resources/resourceGroups@2023-07-01' existing = {
  name: rgName
  scope: subscription(otherSubscriptionId)
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
  scope: resourceGroup(keyVaultResourceGroup)
}
```

### Extension Resources

```bicep
resource lock 'Microsoft.Authorization/locks@2020-05-01' = {
  name: 'doNotDelete'
  scope: storageAccount
  properties: {
    level: 'CanNotDelete'
    notes: 'Production storage - deletion prohibited'
  }
}
```

---
[Back to Overview](./OVERVIEW.md)
