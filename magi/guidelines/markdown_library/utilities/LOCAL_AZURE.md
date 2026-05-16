# Local Azure Services

### Configuration Schema

| File | Purpose |
|:-----|:--------|
| `local-azure-services.json` | Master configuration: all local service endpoints, ports, credentials, container configurations. Structured by service category (storage, messaging, database) |
| `local-azure-services.env` | Flattened environment variable version of the JSON configuration. Used when JSON parsing is unavailable |

### Language-Specific Configuration Loaders

| Language | Loader | Mechanism |
|:---------|:-------|:----------|
| C# | `LocalAzureServicesConfig.cs` | Record-based models with `System.Text.Json`; `Load()` auto-discovers config relative to solution root |
| Python | `local_azure_services_config.py` | Dataclass-based models with JSON loading; type hints for IDE support |
| Rust | `local_azure_services_config.rs` | Serde-based structs with derive macros; `AzureServicesConfig::load()` |

### Service Configuration Structure

```json
{
  "version": "1.0",
  "environment": "local",
  "services": {
    "storage": {
      "blobStorage": { "host": "localhost", "port": 10000 },
      "tableStorage": { "host": "localhost", "port": 10002 }
    },
    "messaging": {
      "serviceBus": { "host": "localhost", "port": 5672 },
      "eventGrid": { "host": "localhost", "port": 5000 }
    },
    "database": {
      "cosmosdb": { "host": "localhost", "port": 8081 },
      "postgres": { "host": "localhost", "port": 5432 }
    }
  }
}
```

### Root Environment Loader

```bash
source .utilities/.local_azure/root_env_loader.sh
# Azure Storage connection string now in $AZURE_STORAGE_CONNECTION_STRING
```

`root_env_loader.sh` loads the local Azure configuration and exports connection strings to the shell environment.

---
[Back to Overview](./OVERVIEW.md)
