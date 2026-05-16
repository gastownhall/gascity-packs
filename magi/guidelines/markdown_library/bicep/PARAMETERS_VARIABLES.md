# Parameters and Variables

### Parameter Design

Parameters define deployment-time inputs. Design parameters to minimize required inputs while enabling necessary customization.

- **Required parameters**: Values that genuinely vary per deployment and have no sensible default.
- **Optional parameters with defaults**: Values that typically remain constant but might need override.

### Decorators

Use decorators to constrain inputs and document intent:

```bicep
@description('The Azure region for resource deployment')
@allowed(['eastus', 'eastus2', 'westus2', 'westeurope'])
param location string

@description('The SKU for the App Service Plan')
@allowed(['B1', 'B2', 'S1', 'S2', 'P1v3', 'P2v3'])
param appServicePlanSku string = 'S1'

@description('Storage account name (3-24 lowercase alphanumeric)')
@minLength(3)
@maxLength(24)
param storageAccountName string

@description('Administrator password for SQL Server')
@secure()
@minLength(8)
param sqlAdminPassword string

@description('Enable diagnostic logging')
param enableDiagnostics bool = true

@description('Number of instances to deploy')
@minValue(1)
@maxValue(10)
param instanceCount int = 2
```

### Parameter Files

Use `.bicepparam` files (Bicep-native) or `.parameters.json` (ARM-compatible) for environment-specific values:

```bicep
using '../main.bicep'

param environment = 'prod'
param location = 'eastus2'
param appServicePlanSku = 'P2v3'
param enableDiagnostics = true
```

### Variables

Variables compute values from parameters, resource properties, or expressions. Use variables to:
- Avoid repeating complex expressions
- Construct resource names from conventions
- Format tags consistently
- Compute derived configuration

```bicep
var resourceSuffix = '${workload}-${environment}-${location}'
var storageAccountName = 'st${replace(resourceSuffix, '-', '')}001'
var defaultTags = {
  Environment: environment
  Workload: workload
  ManagedBy: 'Bicep'
  DeployedAt: utcNow('yyyy-MM-dd')
}
```

### Parameter vs Variable Decision

| Use **parameters** when... | Use **variables** when... |
|:---------------------------|:--------------------------|
| Value varies between deployments or environments | Value is computed from other values |
| Value must be provided by the deployer | Value is constant within the template |
| Value is a secret (with `@secure()`) | Value is derived from resource properties |

### Secure Parameters

**Mark sensitive parameters with `@secure()`. Mandatory for:**
- Passwords
- API keys
- Connection strings

**Hardcoded secrets in templates are forbidden.**

---
[Back to Overview](./OVERVIEW.md)
