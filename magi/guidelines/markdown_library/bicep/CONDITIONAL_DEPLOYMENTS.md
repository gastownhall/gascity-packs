# Conditional Deployments

### Conditional Resources

Deploy resources based on parameter values:

```bicep
param enableDiagnostics bool = true
param deployRedundantResources bool = false

resource diagnosticSetting 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (enableDiagnostics) {
  name: '${appService.name}-diagnostics'
  scope: appService
  properties: {
    workspaceId: logAnalyticsWorkspace.id
    logs: [
      { category: 'AppServiceHTTPLogs', enabled: true }
      { category: 'AppServiceConsoleLogs', enabled: true }
    ]
  }
}

resource secondaryAppService 'Microsoft.Web/sites@2023-01-01' = if (deployRedundantResources) {
  name: '${appName}-secondary'
  location: secondaryLocation
  properties: { /* ... */ }
}
```

### Conditional Modules

```bicep
param enablePrivateEndpoints bool = true
param deployMonitoring bool = true

module privateDns 'modules/networking/privateDns.bicep' = if (enablePrivateEndpoints) {
  name: 'privateDns-${uniqueString(resourceGroup().id)}'
  params: {
    zoneName: 'privatelink.blob.core.windows.net'
    vnetId: vnet.id
  }
}

module monitoring 'modules/monitoring/applicationInsights.bicep' = if (deployMonitoring) {
  name: 'monitoring-${uniqueString(resourceGroup().id)}'
  params: {
    workspaceName: logAnalyticsWorkspaceName
    appInsightsName: applicationInsightsName
  }
}
```

### Ternary Expressions for Property-Level Conditionals

```bicep
resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: appServicePlanName
  location: location
  sku: {
    name: environment == 'prod' ? 'P2v3' : 'B1'
    tier: environment == 'prod' ? 'PremiumV3' : 'Basic'
    capacity: environment == 'prod' ? 3 : 1
  }
  properties: {
    reserved: true
    zoneRedundant: environment == 'prod' ? true : false
  }
}
```

### Null-Coalescing and Safe Navigation

```bicep
var effectiveLocation = customLocation ?? resourceGroup().location
var subnetId = existingSubnet.?id ?? newSubnet.id
```

---
[Back to Overview](./OVERVIEW.md)
