# Loops and Iterations

### Resource Loops

```bicep
param containerNames array = ['data', 'logs', 'backups']

resource containers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = [for name in containerNames: {
  parent: blobService
  name: name
  properties: {
    publicAccess: 'None'
  }
}]

// Access individual loop items
output firstContainerId string = containers[0].id
output allContainerIds array = [for i in range(0, length(containerNames)): containers[i].id]
```

### Index-Based Loops

```bicep
param vmCount int = 3

resource virtualMachines 'Microsoft.Compute/virtualMachines@2023-07-01' = [for i in range(0, vmCount): {
  name: 'vm-${workload}-${padLeft(i + 1, 3, '0')}'
  location: location
  properties: { /* VM configuration */ }
}]
```

### Filtered Loops

```bicep
param databases array = [
  { name: 'orders', tier: 'Standard', size: 'S2' }
  { name: 'analytics', tier: 'Premium', size: 'P1' }
  { name: 'staging', tier: 'Basic', size: 'B' }
]

// Deploy only premium databases
resource premiumDatabases 'Microsoft.Sql/servers/databases@2023-02-01-preview' = [for db in filter(databases, d => d.tier == 'Premium'): {
  parent: sqlServer
  name: db.name
  sku: { name: db.size, tier: db.tier }
}]

// Deploy all databases with conditional properties
resource allDatabases 'Microsoft.Sql/servers/databases@2023-02-01-preview' = [for db in databases: {
  parent: sqlServer
  name: db.name
  sku: { name: db.size, tier: db.tier }
  properties: {
    requestedBackupStorageRedundancy: db.tier == 'Premium' ? 'Geo' : 'Local'
  }
}]
```

### Module Loops

```bicep
param services array = [
  { name: 'api', sku: 'P1v3' }
  { name: 'worker', sku: 'B2' }
  { name: 'frontend', sku: 'S1' }
]

module appServices 'modules/compute/appService.bicep' = [for svc in services: {
  name: 'appService-${svc.name}'
  params: {
    appName: '${workload}-${environment}-${svc.name}'
    sku: svc.sku
  }
}]
```

### Multi-Region Module Loops with Self-Reference

```bicep
param regions array = [
  { name: 'eastus', isPrimary: true }
  { name: 'westus2', isPrimary: false }
  { name: 'westeurope', isPrimary: false }
]

module regionalDeployments 'modules/regional/infrastructure.bicep' = [for region in regions: {
  name: 'infrastructure-${region.name}'
  params: {
    location: region.name
    isPrimary: region.isPrimary
    replicationSource: region.isPrimary ? '' : regionalDeployments[0].outputs.storageAccountId
  }
}]
```

### Nested Loops

Bicep supports nested loops through module composition. The outer loop deploys modules; each module can contain its own loops. **Direct nested loops in resource declarations are not supported.**

---
[Back to Overview](./OVERVIEW.md)
