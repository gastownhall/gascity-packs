# Multi-Environment Strategy

### Store Topology Options

| Topology | Use Case | Benefits | Risks |
|:---------|:---------|:---------|:------|
| Single store, multiple labels | Simple applications | Simplest management; single pane | Requires careful RBAC; label misconfiguration risk |
| Store per environment | High isolation | Strongest isolation; no cross-environment risk | Higher overhead; sync needed |
| **Hybrid** (recommended) | Most apps | Dev/staging share store with labels; production isolated | — |

### Recommended Topology

Production workloads require **dedicated Key Vaults**. Configuration stores may share with labels, but Key Vault isolation prevents:
- Development credential leakage to production
- Accidental production secret access from development contexts
- Compliance violations from mixed-environment secret storage

```
Development:
├── App Configuration: shared-config (Label: Development)
└── Key Vault: kv-orderservice-dev-eus-001

Staging:
├── App Configuration: shared-config (Label: Staging)
└── Key Vault: kv-orderservice-stg-eus-001

Production:
├── App Configuration: appcs-orderservice-prod-eus  (dedicated)
└── Key Vault:        kv-orderservice-prod-eus-001  (dedicated)
```

### Configuration Promotion

**Never copy configuration values manually between environments.** Use infrastructure as code:

```text
Step 1: Define configuration in source control (Terraform, Bicep, App Config import files)
Step 2: Submit changes via pull request
Step 3: Review and approval gates for production changes
Step 4: CI/CD pipeline applies changes to target environment
Step 5: Automated validation and rollback capability
```

This approach provides:
- Change history in source control
- Review process for configuration changes
- Consistent configuration structure across environments
- Rollback capability via source control history

---
[Back to Overview](./OVERVIEW.md)
