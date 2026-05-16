# ARM/Bicep Parameter Patterns

### Bicep Parameter Files

Use environment-specific `.bicepparam` files:

```text
parameters.production.bicepparam
parameters.staging.bicepparam
parameters.development.bicepparam
```

### Parameter Naming

**camelCase for all parameters**:

```bicep
// Correct
param storageAccountName string

// Wrong
param StorageAccountName string
```

### Secure Parameters

**Sensitive parameters must use the `@secure()` decorator**:

```bicep
@secure()
param databasePassword string

@secure()
param apiKey string
```

### Key Vault Integration in Bicep

Use `az.getSecret()` for parameter file Key Vault references:

```bicep
param sqlAdminPassword string = az.getSecret(
  subscription().subscriptionId,
  'rg-shared-prod',
  'kv-shared-prod',
  'sql-admin-password'
)
```

### ARM Parameter Structure

| Section | Contents |
|:--------|:---------|
| `general` | Resource names, locations, tags |
| `networking` | VNet, subnet, NSG configurations |
| `compute` | VM sizes, scale settings |
| `storage` | Account types, replication |
| `security` | Key Vault references, identities |

### ARM Key Vault Reference

```json
{
  "reference": {
    "keyVault": {
      "id": "/subscriptions/{subscription}/resourceGroups/{rg}/providers/Microsoft.KeyVault/vaults/{vault}"
    },
    "secretName": "{secret-name}",
    "secretVersion": "{optional-version}"
  }
}
```

---
[Back to Overview](./OVERVIEW.md)
