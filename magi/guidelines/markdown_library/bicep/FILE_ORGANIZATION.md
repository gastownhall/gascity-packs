# File Organization and Structure

### Directory Layout

```
infrastructure/
├── main.bicep                    # Orchestration entry point
├── bicepconfig.json              # Linter and compilation settings
├── parameters/
│   ├── dev.bicepparam            # Development environment parameters
│   ├── staging.bicepparam        # Staging environment parameters
│   └── prod.bicepparam           # Production environment parameters
├── modules/
│   ├── networking/
│   │   ├── vnet.bicep
│   │   ├── nsg.bicep
│   │   └── privateEndpoint.bicep
│   ├── compute/
│   │   ├── appService.bicep
│   │   ├── functionApp.bicep
│   │   └── containerApp.bicep
│   ├── data/
│   │   ├── cosmosDb.bicep
│   │   ├── sqlServer.bicep
│   │   └── storageAccount.bicep
│   └── security/
│       ├── keyVault.bicep
│       ├── managedIdentity.bicep
│       └── roleAssignment.bicep
└── scripts/
    ├── deploy.sh
    └── validate.sh
```

### File Naming Conventions

| Pattern | Purpose |
|:--------|:--------|
| `main.bicep` | Main orchestration file |
| `camelCase.bicep` | Module file matching primary resource type (`storageAccount.bicep`, `appServicePlan.bicep`) |
| `{environment}.bicepparam` | Parameter file (or `{environment}.parameters.json` for ARM-compatible) |
| `bicepconfig.json` | Configuration at repository root |

### Single Responsibility

Each module encapsulates one logical resource or tightly coupled resource group:
- `storageAccount.bicep` — Storage account with containers and access policies
- `appService.bicep` — App Service, deployment slots, and associated configuration
- `sqlServer.bicep` — SQL Server, databases, firewall rules, and auditing

**Do not create monolithic modules that deploy entire environments.** Compose granular modules in orchestration files.

### bicepconfig.json

Configure linting rules and experimental features at the repository level:

```json
{
  "analyzers": {
    "core": {
      "enabled": true,
      "rules": {
        "no-hardcoded-location": {
          "level": "error",
          "disalloweLocations": ["northcentralus", "southcentralus"]
        },
        "no-unused-params": { "level": "error" },
        "no-unused-vars": { "level": "error" },
        "prefer-interpolation": { "level": "warning" },
        "secure-secrets-in-params": { "level": "error" },
        "use-resource-symbol-reference": { "level": "warning" },
        "explicit-values-for-loc-params": { "level": "warning" },
        "no-unnecessary-dependsOn": { "level": "warning" },
        "simplify-interpolation": { "level": "info" },
        "use-recent-api-versions": {
          "level": "warning",
          "maxAllowedAgeInDays": 365
        },
        "use-stable-api-version": { "level": "warning" },
        "admin-username-should-not-be-literal": { "level": "error" },
        "max-outputs": { "level": "warning", "maxAllowedOutputs": 64 },
        "max-params": { "level": "warning", "maxAllowedParams": 256 },
        "max-resources": { "level": "warning", "maxAllowedResources": 800 },
        "max-variables": { "level": "warning", "maxAllowedVariables": 256 }
      }
    }
  },
  "experimentalFeaturesEnabled": {
    "userDefinedTypes": true,
    "userDefinedFunctions": true,
    "extensibility": true,
    "resourceDerivedTypes": true,
    "symbolicNameCodegen": true
  }
}
```

---
[Back to Overview](./OVERVIEW.md)
