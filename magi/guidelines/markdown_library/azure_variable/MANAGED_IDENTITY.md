# Managed Identity Patterns

### Identity Types

| Type | Lifecycle | Management | Use Case | Note |
|:-----|:----------|:-----------|:---------|:-----|
| System-assigned | Tied to resource | Automatic | Single-purpose resources | One identity per resource |
| User-assigned | Independent | Explicit | Shared permissions across resources | Survives resource recreation |

Prefer system-assigned for single-purpose resources. Use user-assigned when multiple resources require identical permissions or when identity must survive resource recreation.

### Authentication Priority

| Priority | Method | Scenario |
|:---------|:-------|:---------|
| 1 | Managed Identity | Azure-hosted workloads |
| 2 | Workload Identity Federation | Kubernetes / external |
| 3 | Service Principal with Certificate | Pipeline authentication |
| 4 | Service Principal with Secret | Legacy / last resort |

With managed identity, applications authenticate to Key Vault and App Configuration **without credentials**. The identity itself requires no secret — Azure handles authentication transparently.

### `DefaultAzureCredential` Chain Order

| Order | Credential | Notes |
|:------|:-----------|:------|
| 1 | EnvironmentCredential | Environment variables |
| 2 | WorkloadIdentityCredential | Kubernetes / federated |
| 3 | ManagedIdentityCredential | Azure-hosted |
| 4 | AzureCliCredential | Local dev |
| 5 | AzurePowerShellCredential | Local dev |
| 6 | InteractiveBrowserCredential | Development only |

For production, the chain is appropriate as-is. For development, consider `AzureCliCredential` directly to avoid unexpected credential selection.

---
[Back to Overview](./OVERVIEW.md)
