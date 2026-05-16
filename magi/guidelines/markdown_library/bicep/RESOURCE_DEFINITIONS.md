# Resource Definitions

### Resource Declaration Structure

Every resource declaration follows this pattern:

```bicep
resource <symbolicName> '<resourceType>@<apiVersion>' = {
  name: <resourceName>
  location: <location>
  tags: <tags>
  properties: {
    // Resource-specific configuration
  }
}
```

### API Version Selection

- Use the latest stable API version unless specific functionality requires otherwise
- **No `-preview` API versions** unless required and documented
- Document API version choices when not using latest
- Update API versions during regular maintenance cycles
- Test API version upgrades in non-production before rollout

### Property Completeness

Set all properties relevant to your deployment explicitly. **Do not rely on Azure defaults**:

```bicep
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
      virtualNetworkRules: []
      ipRules: []
    }
    encryption: {
      services: {
        blob: { enabled: true }
        file: { enabled: true }
      }
      keySource: 'Microsoft.Storage'
    }
  }
}
```

### Child Resources

Define child resources using the `parent` property:

```bicep
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 7
    }
  }
}

resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'data'
  properties: {
    publicAccess: 'None'
  }
}
```

### Existing Resources

Reference pre-existing resources without deploying them:

```bicep
resource existingVnet 'Microsoft.Network/virtualNetworks@2023-05-01' existing = {
  name: vnetName
  scope: resourceGroup(networkingResourceGroup)
}

resource subnet 'Microsoft.Network/virtualNetworks/subnets@2023-05-01' existing = {
  parent: existingVnet
  name: subnetName
}
```

---
[Back to Overview](./OVERVIEW.md)
