# Dependencies and Ordering

### Implicit Dependencies (Preferred)

Bicep automatically creates dependencies when one resource references another's properties:

```bicep
resource appService 'Microsoft.Web/sites@2023-01-01' = {
  name: appName
  properties: {
    serverFarmId: appServicePlan.id  // Implicit dependency on appServicePlan
  }
}
```

### Explicit Dependencies

Use `dependsOn` only when no property reference exists but ordering is required:

```bicep
resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, appService.id, 'StorageBlobDataContributor')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: appService.identity.principalId
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    appService  // Explicit: need identity to exist, but no property reference forces it
  ]
}
```

### Deployment Sequencing

Azure Resource Manager deploys independent resources in parallel. Dependencies create sequential ordering. Design resource graphs for maximum parallelism:
- Group independent resources without artificial dependencies
- Chain dependent resources through property references
- Use modules to encapsulate dependency groups

### Circular Dependencies

Circular dependencies cause deployment failures. Common causes:
- Two resources referencing each other's IDs
- Network resources with bidirectional rules
- Key Vault with access policies referencing identities that need Key Vault

Resolution: break cycles with deployment ordering, existing resource references, or restructured resource definitions.

---
[Back to Overview](./OVERVIEW.md)
