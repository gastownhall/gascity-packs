# Variable-Restructure Shakedown

### Scope

Targeted variable-change shakedown. This section is **narrow** and applies only after a rename or restructure of the Azure variable set:

- App Configuration keys
- Key Vault secret names
- Bicep parameter names
- ARM parameter names
- Terraform variable names
- Pipeline variable group entries

It is **not** a full infrastructure shakedown — whole-stack post-deploy validation belongs in `bicep_guidelines`. The concern here is a single question: **after renaming, does every downstream reference still resolve and bind correctly?**

### Definition

A variable-restructure shakedown is the controlled validation that every ARM/Bicep/Terraform reference, every pipeline variable consumer, and every application configuration lookup still resolves against the renamed variable set, and that a deployment executed with the new variable scheme wires up correctly in a sandbox subscription.

It is **not a naming-convention lint** — that is preflight.

### Phases

| Phase | Scope | Timing |
|:------|:------|:-------|
| **Preflight** | Static naming-convention lint, required-tag presence, resource-name regex validation, Bicep linter, `terraform fmt`/`validate` | Runs before shakedown |
| **Shakedown** | Live resolution of every variable reference, sandbox-subscription `what-if`/`plan` and deploy, confirmation that every consumer reads the intended value | After rename PR merges to integration branch, before promotion to staging |
| **Testing** | Full behavioral and performance validation | Out of scope for this section |

### Triggers

- Any PR that renames an App Configuration key already referenced by a running service
- Any PR that renames a Key Vault secret referenced by App Configuration via `keyvaultref`
- Any PR that renames a Bicep parameter, ARM parameter, or Terraform variable consumed by a pipeline variable group
- Any PR that restructures label usage (e.g., splits Development/Staging into distinct labels)
- Any PR that changes the `FeatureManagement` flag naming prefix
- Any PR that migrates secrets between vaults or renames the vault referenced in `keyvaultref` URIs

### Non-Triggers

- Adding a new variable that no existing consumer references
- Updating a variable value without changing its name or type
- Editing documentation or naming-convention tables in this file

### Validation Checks

| Check | Description |
|:------|:------------|
| ARM/Bicep resolution | Every `param` reference and `az.getSecret` call resolves; `az bicep build` + `az deployment group what-if` against sandbox produces no `ResourceNotFound` / `ParameterNotFound` / `SecretNotFound` |
| Pipeline reference integrity | Every pipeline step that consumes a renamed variable resolves it; grep all pipeline YAML in importing repos for the old name |
| App Config keyvaultref resolution | Every entry of content-type `application/vnd.microsoft.appconfig.keyvaultref+json` resolves to an existing secret; sandbox `DefaultAzureCredential` lookup returns non-empty value |
| Label propagation | Every consumer of the restructured label set reads the expected label at runtime; a `SelectsLabelFilter` pointing at an old label silently falls through to unlabeled defaults |
| Feature flag prefix | After a `FeatureManagement` prefix change, every `IFeatureManager` consumer resolves the new key; sandbox feature-flag endpoint asserts state matches expected |
| Sandbox deploy wiring | A fresh deployment to a throwaway sandbox subscription succeeds; deployed resources reference the expected Key Vault, App Configuration store, and managed identity |

### Execution Principles

- **Conservative** — the rename is the only change under validation. Do not stack unrelated variable edits into the shakedown PR.
- **Bounded** — deploy only to a dedicated sandbox subscription with its own Key Vault, App Configuration store, and identity; never against staging or production.
- **Observable** — every lookup, what-if, and deploy step emits a structured log entry captured to an artifact.
- **Known-good input** — use a committed fixture listing the old-name → new-name mapping and expected resolved values.
- **No optimization** — do not tune throttling, retry, or caching while the rename shakedown is in progress.

### Execution Sequence

```text
Step 1: Confirm preflight passes — naming-convention lint, Bicep build, Terraform validate
Step 2: Initialize the sandbox subscription — fresh resource group, fresh App Configuration store, fresh Key Vault seeded with known-good secret set
Step 3: Execute `az deployment group what-if` with renamed parameter files; confirm no ResourceNotFound/ParameterNotFound/SecretNotFound
Step 4: Execute the deployment end-to-end against the sandbox
Step 5: Iterate the rename-mapping fixture; issue a resolution probe for every entry against sandbox App Configuration and Key Vault
Step 6: Tear down the sandbox resource group
Step 7: Record probe log, what-if output, deployment correlation id, and classification
```

### Result Classification

- **pass** — Every rename entry resolved, what-if reported no missing references, sandbox deployment succeeded, every consumer read the expected value. Promote the PR.
- **fail-blocking** — A reference did not resolve, a secret lookup returned `NotFound`/`Forbidden`, what-if reported an unexpected delete, or a pipeline step consumed the old name. Revert the rename or complete the missed consumers before promotion.
- **fail-nonblocking** — A non-critical documentation key still references the old name, or a non-enforced tag drifted. Open an issue and promote with tracked follow-up.
- **inconclusive** — Sandbox subscription unreachable or rate-limit prevented completion. Re-run after the environment condition is resolved.

### Required Artifacts

- Rename mapping fixture (old-name → new-name → expected-value) committed to the PR
- `az deployment group what-if` output
- Sandbox deployment correlation id and activity log
- Probe log showing resolution results for every rename entry
- Environment snapshot: sandbox subscription id, resource group name, App Configuration endpoint, Key Vault URI, timestamp

### Anti-Patterns (Forbidden)

- Treating the naming-convention lint as sufficient — it catches format drift, not broken references
- Running the rename shakedown against staging or production instead of a sandbox subscription
- Bundling unrelated variable edits into the rename PR
- Skipping the pipeline-YAML grep step — downstream pipelines in other repositories silently break on the old name
- Discarding the probe log at job exit

### Reference Rename-Mapping Fixture

```yaml
# shakedown/rename-mapping.yaml — old-to-new variable mapping for this PR
renames:
  - kind: appconfig-key
    old: OrderService:Database:ConnectionTimeout
    new: OrderService:Sql:ConnectionTimeoutSeconds
    expected_value: "30"
    label: Production
  - kind: keyvault-secret
    old: orderservice-prod-dbpassword
    new: orderservice-prod-sql-admin-password
    expected_reference: "https://kv-orderservice-prod-eus-001.vault.azure.net/secrets/orderservice-prod-sql-admin-password"
  - kind: bicep-param
    old: databasePassword
    new: sqlAdminPassword
    consumers:
      - infra/main.bicep
      - infra/modules/sql.bicep
  - kind: pipeline-var
    old: ORDER_DB_PASSWORD
    new: ORDER_SQL_ADMIN_PASSWORD
    variable_group: order-service-prod
```

### Cross-References

- `bicep_guidelines` — Full infrastructure post-deploy shakedown (not covered here)
- `cicd_guidelines` — Pipeline-stage shakedown that runs the renamed variable set through the build/deploy path

---
[Back to Overview](./OVERVIEW.md)
