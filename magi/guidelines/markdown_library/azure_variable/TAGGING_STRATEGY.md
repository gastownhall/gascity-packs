# Tagging Strategy

### Required Tags

| Tag | Required | Values | Purpose |
|:----|:---------|:-------|:--------|
| `Environment` | Yes | `Development` / `Staging` / `Production` / `DR` | Deployment environment |
| `Application` | Yes | — | Application or service name |
| `Owner` | Yes | — | Business owner email or team alias |
| `CostCenter` | Yes | — | Financial cost center for billing |
| `Department` | Yes | — | Department responsible for the resource |
| `CreatedDate` | Yes | `YYYY-MM-DD` | Resource creation date |
| `DataClassification` | No | `Public` / `Internal` / `Confidential` / `Restricted` | Data sensitivity |
| `Compliance` | No | `PCI` / `HIPAA` / `SOC2` / `GDPR` / `None` | Compliance requirements |
| `Backup` | No | `Daily` / `Weekly` / `Monthly` / `None` | Backup schedule |

### Tag Governance

- **Azure Policy** at the resource group level **denies resource creation** without required tags.
- **Tag inheritance** — resources inherit tags from resource group unless overridden.

---
[Back to Overview](./OVERVIEW.md)
