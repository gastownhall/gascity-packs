# Type System and User-Defined Types

### Built-In Types

| Type | Description |
|:-----|:------------|
| `string` | Text values |
| `int` | Integer numbers |
| `bool` | Boolean true/false |
| `array` | Ordered collections |
| `object` | Key-value structures |

### Type Annotations

```bicep
param names array
param config object
param count int
param enabled bool
param name string
```

### User-Defined Types

```bicep
type appServiceConfig = {
  name: string
  sku: 'B1' | 'B2' | 'S1' | 'S2' | 'P1v3' | 'P2v3'
  alwaysOn: bool
  minInstances: int?
  maxInstances: int?
  customDomains: string[]?
}

type databaseConfig = {
  name: string
  tier: 'Basic' | 'Standard' | 'Premium'
  @minValue(1)
  @maxValue(100)
  dtuCapacity: int
  backupRetentionDays: int?
  geoReplication: bool
}

param appConfigurations appServiceConfig[]
param databaseConfigurations databaseConfig[]
```

### Discriminated Unions

```bicep
type publicEndpoint = {
  type: 'public'
  allowedIpRanges: string[]
}

type privateEndpoint = {
  type: 'private'
  subnetId: string
  privateDnsZoneId: string?
}

type endpointConfig = publicEndpoint | privateEndpoint

param endpoint endpointConfig
```

---
[Back to Overview](./OVERVIEW.md)
