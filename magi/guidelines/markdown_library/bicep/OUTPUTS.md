# Outputs

### Output Purpose

Outputs expose values from deployed resources for:
- Consumption by dependent deployments
- CI/CD pipeline integration
- Post-deployment configuration
- Documentation and reporting

### Output Design

Declare outputs with descriptions and appropriate visibility:

```bicep
@description('The resource ID of the storage account')
output storageAccountId string = storageAccount.id

@description('The primary blob endpoint')
output blobEndpoint string = storageAccount.properties.primaryEndpoints.blob

@description('The managed identity principal ID')
output principalId string = appService.identity.principalId

@description('Connection string for application configuration')
@secure()
output connectionString string = 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value}'
```

### Output Chaining Across Modules

```bicep
// Module A outputs
output vnetId string = vnet.id
output subnetIds array = [for subnet in subnets: subnet.id]

// Module B consumes Module A outputs
module moduleB 'moduleB.bicep' = {
  name: 'moduleB'
  params: {
    vnetId: moduleA.outputs.vnetId
    subnetId: moduleA.outputs.subnetIds[0]
  }
}

// Module C consumes both
module moduleC 'moduleC.bicep' = {
  name: 'moduleC'
  params: {
    networkConfig: {
      vnetId: moduleA.outputs.vnetId
      appGatewaySubnetId: moduleA.outputs.subnetIds[1]
      privateEndpointId: moduleB.outputs.privateEndpointId
    }
  }
}
```

### Secure Outputs

Mark sensitive outputs with `@secure()`. Secure outputs:
- Do not appear in deployment logs
- Require explicit handling in consuming templates
- **Should be minimized — prefer Key Vault references over passing secrets through outputs**

### Output Aggregation

When deploying multiple instances, output arrays or objects:

```bicep
output storageAccountIds array = [for (account, i) in storageAccounts: {
  name: account.name
  id: storageAccountResources[i].id
}]
```

---
[Back to Overview](./OVERVIEW.md)
