# Deployment Stacks

Deployment Stacks provide lifecycle management for groups of related resources, with deny-settings to prevent unmanaged drift.

### Creation with Deny Settings

```bash
az stack group create \
  --name production-stack \
  --resource-group myResourceGroup \
  --template-file main.bicep \
  --parameters @parameters/prod.bicepparam \
  --deny-settings-mode DenyDelete \
  --deny-settings-apply-to-child-scopes
```

### Action on Unmanage

```bash
az stack group create \
  --name production-stack \
  --resource-group myResourceGroup \
  --template-file main.bicep \
  --parameters @parameters/prod.bicepparam \
  --action-on-unmanage DetachAll \
  --deny-settings-mode DenyWriteAndDelete
```

### Updates with What-If

```bash
# Preview changes
az stack group create \
  --name production-stack \
  --resource-group myResourceGroup \
  --template-file main.bicep \
  --parameters @parameters/prod.bicepparam \
  --what-if

# Apply with explicit unmanage action
az stack group create \
  --name production-stack \
  --resource-group myResourceGroup \
  --template-file main.bicep \
  --parameters @parameters/prod.bicepparam \
  --action-on-unmanage Detach
```

---
[Back to Overview](./OVERVIEW.md)
