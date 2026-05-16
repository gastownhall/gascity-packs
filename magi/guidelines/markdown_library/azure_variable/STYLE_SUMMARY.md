# Style Summary

| Element | Required Style |
|:--------|:---------------|
| Resource Names | `{abbr}-{app}-{env}-{region}-{instance}`; per-resource length and charset constraints |
| Tags | `Environment`, `Application`, `Owner`, `CostCenter`, `Department`, `CreatedDate` required; policy-enforced |
| Secret Storage | Key Vault exclusively; never App Configuration or source control |
| Configuration Storage | App Configuration for non-sensitive values; Key Vault references for secrets |
| Environment Segregation | Labels in App Configuration; **dedicated Key Vault for production** |
| Authentication | Managed identity preferred; service principal certificate if required |
| Permission Model | Azure RBAC; never legacy access policies |
| Network Security | Private endpoints for production; firewall rules as fallback |
| Monitoring | Sentinel integration required; diagnostic logs to Log Analytics |
| Secret Lifecycle | Expiration dates on all secrets; automated rotation |
| Configuration Refresh | Sentinel-key pattern; ≥ 5 min intervals |
| Feature Flags | `FeatureManagement:` prefix; explicit cleanup post-GA |
| Bicep | camelCase params; `@secure()` for sensitive; `az.getSecret()` for KV references |
| Disaster Recovery | Geo-replication for App Configuration; documented Key Vault recovery |
| Access Control | Least privilege; quarterly review; scoped permissions |
| Infrastructure as Code | All configuration and vault resources defined in source control |
| Secret References | Key Vault references in App Configuration for bridging |
| Compliance | SOC 2 / PCI-DSS / HIPAA / GDPR audit, retention, rotation requirements |
| Shakedown | Rename PRs run sandbox-subscription what-if + deploy + per-entry probe; classified outcome |
| Defense in Depth | Turnkey scripts + input validation + dry-run + audit + idempotency + scoped SPs + policy/locks + shakedown |

---

Following these guidelines produces configuration and secret management implementations that are secure, auditable, operationally sound, and cost-effective. Secrets never appear where they shouldn't. Configuration changes flow through controlled processes. Sentinel provides the security visibility required for production operations. The separation between configuration and secrets remains clear, enabling appropriate access control and lifecycle management for each category.

**Apply this guidance universally to all Azure App Configuration, Key Vault, and infrastructure parameter implementations across the organization.**

---
[Back to Overview](./OVERVIEW.md)
