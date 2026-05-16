# Functions and Expressions

### Built-In Functions

| Category | Functions |
|:---------|:----------|
| String manipulation | `concat()`, `substring()`, `replace()`, `toLower()`, `toUpper()`, `trim()` |
| Array operations | `first()`, `last()`, `length()`, `contains()`, `empty()`, `union()`, `intersection()` |
| Resource functions | `resourceGroup()`, `subscription()`, `tenant()`, `resourceId()`, `subscriptionResourceId()` |
| Date/time | `utcNow()`, `dateTimeAdd()` |
| Deployment | `deployment()`, `environment()` |
| Cryptographic | `uniqueString()`, `guid()`, `newGuid()` |

### Resource Functions

```bicep
var storageKeys = storageAccount.listKeys()
var primaryKey = storageKeys.keys[0].value

var cosmosKeys = cosmosAccount.listKeys()
var primaryMasterKey = cosmosKeys.primaryMasterKey
```

### String Interpolation

**Prefer interpolation over `concat()`**:

```bicep
// Preferred
var resourceName = '${workload}-${environment}-${resourceType}'

// Avoid
var resourceName = concat(workload, '-', environment, '-', resourceType)
```

### User-Defined Functions

```bicep
func formatResourceName(workload string, env string, type string, instance int) string =>
  '${workload}-${env}-${type}-${padLeft(string(instance), 3, '0')}'

func buildConnectionString(server string, database string, useAAD bool) string =>
  useAAD
    ? 'Server=${server};Database=${database};Authentication=Active Directory Integrated;'
    : 'Server=${server};Database=${database};Integrated Security=SSPI;'

var appServiceName = formatResourceName(workloadName, environment, 'app', 1)
var connectionString = buildConnectionString(sqlServer.properties.fullyQualifiedDomainName, 'mydb', true)
```

---
[Back to Overview](./OVERVIEW.md)
