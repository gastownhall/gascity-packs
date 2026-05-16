# Modules

### Module Purpose

Modules encapsulate related resources into reusable, testable units. A well-designed module:
- Deploys one logical component (not an entire environment)
- Accepts parameters for customization
- Outputs values needed by dependent resources
- Handles its own internal dependencies
- Documents its interface through parameter decorators

### Module Composition

Compose complex infrastructure from granular modules:

```bicep
module networking 'modules/networking/vnet.bicep' = {
  name: 'networking-${uniqueString(resourceGroup().id)}'
  params: {
    vnetName: vnetName
    addressPrefix: '10.0.0.0/16'
    subnets: subnets
  }
}

module database 'modules/data/sqlServer.bicep' = {
  name: 'database-${uniqueString(resourceGroup().id)}'
  params: {
    serverName: sqlServerName
    administratorPassword: sqlAdminPassword
    subnetId: networking.outputs.databaseSubnetId
  }
}

module application 'modules/compute/appService.bicep' = {
  name: 'application-${uniqueString(resourceGroup().id)}'
  params: {
    appName: appServiceName
    subnetId: networking.outputs.appSubnetId
    databaseConnectionString: database.outputs.connectionString
  }
  dependsOn: [
    database
  ]
}
```

### Module Interface Design

Define clear contracts through parameters and outputs:

```bicep
// modules/data/cosmosDb.bicep

@description('Cosmos DB account name')
param accountName string

@description('Azure region for deployment')
param location string = resourceGroup().location

@description('Consistency level for the account')
@allowed(['Eventual', 'Session', 'BoundedStaleness', 'Strong'])
param consistencyLevel string = 'Session'

@description('Enable automatic failover')
param enableAutomaticFailover bool = true

@description('Database names to create')
param databaseNames array = []

@description('Tags to apply to all resources')
param tags object = {}

// ... resource definitions ...

@description('The resource ID of the Cosmos DB account')
output accountId string = cosmosAccount.id

@description('The document endpoint for the account')
output documentEndpoint string = cosmosAccount.properties.documentEndpoint

@description('The primary connection string')
@secure()
output primaryConnectionString string = cosmosAccount.listConnectionStrings().connectionStrings[0].connectionString
```

### Module Registry

For shared modules across repositories, use Bicep registries:

```bicep
// Reference module from Azure Container Registry
module networking 'br:myregistry.azurecr.io/bicep/networking:1.2.0' = {
  name: 'networking'
  params: { /* ... */ }
}

// Reference module from public registry (Azure Verified Modules)
module monitoring 'br/public:avm/ptn/azuremonitor/baseline:0.1.0' = {
  name: 'monitoring'
  params: { /* ... */ }
}
```

### Module Versioning

Version modules semantically:
- **Breaking changes** → increment major version
- **New optional parameters** → increment minor version
- **Bug fixes** → increment patch version

---
[Back to Overview](./OVERVIEW.md)
