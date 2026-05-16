# Post-Deployment Shakedown

### Definition

A Bicep post-deployment shakedown is the controlled validation sequence executed **after** `az deployment group create`, `az deployment sub create`, or `az stack group create` reports success — confirming that every declared resource actually exists, is wired correctly, and is reachable from its declared consumers.

Shakedown is distinct from:
- **`bicep build`** — only compiles ARM JSON
- **`az deployment what-if`** — previews ARM's computed diff but does not execute against the deployed state
- **Application smoke tests** — validate application behavior, not infrastructure wiring

**A `provisioningState` of `Succeeded` is not proof that the deployed resources actually work together.**

### Mandatory Triggers

Shakedown runs after every deployment that:
- Is the **first** deployment of a new Bicep template or module to a resource group
- Changes SKU, tier, or kind on any resource
- Creates a managed identity or rotates a role assignment
- Introduces a Key Vault reference or changes a secret name
- Adds, removes, or reconfigures a private endpoint, VNet integration, or network ACL
- Changes diagnostic settings or Log Analytics workspace
- Moves resources across resource group, subscription, or region
- Bumps the Azure API version for any resource type

### Non-Triggers

- Tag-only updates
- Parameter file comment changes
- No-op redeployments where what-if reports zero changes

### Validation Categories (Ten Failure Surfaces)

1. **Outputs resolution** — Every ARM output declared by the template resolves to a concrete resource ID, endpoint, or value, retrievable from deployment history.
2. **Resource existence** — Every declared resource exists in the expected resource group, under the expected name, with the expected SKU, kind, and location.
3. **Resource wiring** — Downstream consumers resolve upstream producers: Function App `AzureWebJobsStorage` points at the correct storage account, App Service connection strings reference the correct database, Event Grid subscriptions bind to the correct topic.
4. **Key Vault references** — Resolve at runtime for every resource that declares them; the referencing identity has `get` permissions on the secret.
5. **Managed identity** — System-assigned or user-assigned identities are assigned to the target resource and the object ID is retrievable.
6. **RBAC active** — Role assignments exist with the expected principal ID, role definition ID, and scope; `az role assignment list` reflects the live state.
7. **Diagnostic settings** — Attached to the resource and emitting to the configured Log Analytics workspace, Event Hub, or Storage Account.
8. **Private endpoints** — Reach their dependencies via private DNS zones; NSG rules permit the intended traffic.
9. **Network peering** — VNet peerings are `Connected` in both directions; effective routes resolve across the peering.
10. **Monitor alerts** — Azure Monitor alert rules bind to a live metric source and report a valid evaluation state.

### Execution Principles

- **Conservative** — read-only Azure CLI and Azure Resource Graph queries
- **Progressive** — verify existence, then SKU, then wiring, then RBAC, then network reachability, then observability
- **Controlled environment** — a dedicated validation resource group or subscription matching the target SKUs
- **Observable** — capture `az cli --debug` transcripts, deployment operation logs, Resource Graph snapshots
- **Known-good inputs** — expected output values committed to the repository next to the Bicep module
- **No mutation during shakedown** — do not "fix" missed dependencies in place; update the Bicep source

### Execution Sequence

```text
Step 1: Confirm preflight passes — bicep build clean, bicep lint clean, what-if diff matches expectations, parameter file committed
Step 2: Execute the deployment command and capture the deployment name
Step 3: Retrieve outputs via `az deployment group show --query properties.outputs`; assert every declared output has a non-empty value
Step 4: For each output resource ID, call `az resource show` and assert SKU, kind, location
Step 5: Validate wiring — for every reference between resources, query the consumer for the resolved value and match against the producer
Step 6: Validate RBAC — `az role assignment list --scope` for each expected scope; confirm principal and role
Step 7: Validate diagnostic settings — `az monitor diagnostic-settings list` for every resource that declared them
Step 8: Validate private endpoints and network peering via `az network private-endpoint show` and `az network vnet peering show`
Step 9: Record classification and store artifacts alongside the deployment name
```

### Reference Shakedown Script

```bash
#!/usr/bin/env bash
set -euo pipefail
RG="${1:?resource group required}"
DEPLOYMENT="${2:?deployment name required}"
OUT_DIR=".shakedown/${DEPLOYMENT}"
mkdir -p "${OUT_DIR}"

# 1. Capture outputs
az deployment group show \
  --resource-group "${RG}" \
  --name "${DEPLOYMENT}" \
  --query properties.outputs \
  -o json > "${OUT_DIR}/outputs.json"

# 2. Assert every output has a value
jq -e 'to_entries | all(.value.value != null and .value.value != "")' "${OUT_DIR}/outputs.json" \
  || { echo "FAIL: empty deployment output"; exit 1; }

# 3. Verify every resource referenced by an output id exists in RG
jq -r 'to_entries[] | select(.value.value|tostring|startswith("/subscriptions/")) | .value.value' "${OUT_DIR}/outputs.json" \
  | while read -r RID; do
      az resource show --ids "${RID}" --query '{id:id,sku:sku,kind:kind,location:location}' -o json \
        >> "${OUT_DIR}/resources.json" \
        || { echo "FAIL: resource missing ${RID}"; exit 1; }
    done

# 4. Verify RBAC role assignments at the resource group scope
az role assignment list --resource-group "${RG}" -o json > "${OUT_DIR}/rbac.json"

# 5. Verify diagnostic settings emit to Log Analytics for every resource that declared them
jq -r '.[].id' "${OUT_DIR}/resources.json" \
  | while read -r RID; do
      az monitor diagnostic-settings list --resource "${RID}" -o json \
        >> "${OUT_DIR}/diagnostics.json" || true
    done

# 6. Capture deployment operations for the audit trail
az deployment operation group list \
  --resource-group "${RG}" \
  --name "${DEPLOYMENT}" \
  -o json > "${OUT_DIR}/operations.json"

echo "PASS: shakedown ${DEPLOYMENT}"
```

### Result Classification

- **pass** — Every output resolves; every resource exists with expected SKU; every wiring check matches; RBAC is active; diagnostics emit; private endpoints resolve.
- **fail-blocking** — Output is empty, resource is missing or in the wrong group, SKU mismatch, Key Vault reference unresolved, managed identity not assigned, RBAC role assignment missing, private endpoint fails DNS resolution.
- **fail-nonblocking** — Diagnostic settings attached but first metric not yet visible; alert rule created but evaluation window not yet elapsed; tag drift.
- **inconclusive** — Azure Resource Manager throttling, Resource Graph index lag, regional incident blocking verification.

### Required Artifacts

- Deployment name and correlation ID
- `az deployment group show --query properties.outputs` JSON
- `az deployment operation group list` output
- Resource Graph snapshot
- `az role assignment list` for every expected scope
- Git SHA of the Bicep template and parameter file used
- Issue list with reproduction context per anomaly

### Anti-Patterns (Forbidden)

- Assuming `provisioningState` `Succeeded` implies correct wiring
- Running shakedown against a stub resource group with different SKUs than the target
- Skipping Key Vault reference checks because the Key Vault exists
- Mutating resources during shakedown to "fix" missed dependencies instead of updating the Bicep source
- Discarding the deployment outputs and operation log after the run

---
[Back to Overview](./OVERVIEW.md)
