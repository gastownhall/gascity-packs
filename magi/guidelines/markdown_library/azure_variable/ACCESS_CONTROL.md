# Access Control and Identity

### Role-Based Access Control

App Configuration roles:

| Role | Permissions |
|:-----|:------------|
| App Configuration Data Owner | Full read/write on all configuration |
| App Configuration Data Reader | Read-only access to configuration |

Key Vault roles (RBAC model — recommended):

| Role | Permissions |
|:-----|:------------|
| Key Vault Administrator | Full management excluding purge |
| Key Vault Secrets Officer | Manage secrets; cannot manage keys or certificates |
| Key Vault Secrets User | Read secret values only |
| Key Vault Certificates Officer | Manage certificates |
| Key Vault Crypto Officer | Manage keys and perform crypto operations |
| Key Vault Reader | Read metadata; cannot read secret values |

### Access Policies vs RBAC

| Model | Status |
|:------|:-------|
| Access Policies (Legacy) | Per-vault permission grants; all-or-nothing within categories; no inheritance; limited audit integration |
| Azure RBAC (Recommended) | Granular permissions at vault, secret, key, or certificate scope; inheritance from RG/subscription; unified with Azure IAM; required for Sentinel integration |

**Migrate existing vaults from Access Policies to RBAC. New vaults must use RBAC exclusively.**

### Service Principal Configuration

Authenticate using:
1. **Managed Identity** (preferred)
2. **Workload Identity Federation** (Kubernetes; federated trust with external IdPs)
3. **Service Principal with Certificate** (pipelines)
4. **Service Principal with Secret** (least preferred)

Managed identity eliminates an entire category of secret management concerns. Use it unless the workload runs outside Azure or requires cross-tenant access.

### Network Security

Private endpoints eliminate public network exposure:
- App Configuration private endpoint: configuration traffic stays on Azure backbone
- Key Vault private endpoint: secret access never traverses public internet
- Disable public network access after private endpoint configuration
- Configure DNS for private endpoint resolution (Private DNS Zone or custom DNS)

Firewall rules as fallback when private endpoints aren't feasible:
- Allow only specific IP ranges
- Allow trusted Azure services
- Deny all other traffic

---
[Back to Overview](./OVERVIEW.md)
