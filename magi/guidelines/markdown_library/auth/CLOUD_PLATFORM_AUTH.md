# Cloud Platform Authentication

Cloud platforms provide IAM systems for both human operators and machine workloads. Platform-specific patterns differ; principles are shared: **prefer managed identities, scope permissions tightly, and audit access continuously.**

### Azure / Entra ID

- **Use Managed Identity** for Azure-hosted workloads (App Service, Functions, AKS pods, VMs). Eliminates service principal secrets entirely.
  - System-assigned identities — tied to a single resource
  - User-assigned identities — shared across resources with the same access requirements
- **For non-Azure workloads → use Workload Identity Federation** with OIDC token exchange. External IdPs (GitHub Actions, GCP, AWS) issue tokens that Azure trusts without storing Azure credentials externally.
- Scope Azure RBAC to the narrowest resource scope possible: resource > resource group > subscription > management group.
- Enable **Conditional Access policies** for human users: require MFA, restrict by location, enforce device compliance, block legacy auth protocols.
- Use **Azure Key Vault** for secrets, certificates, and encryption keys. Grant access via Key Vault RBAC (preferred) or access policies. Reference from App Service / Functions / AKS via native integration.

### AWS IAM

- **Use IAM Roles** for AWS-hosted workloads: EC2 instance profiles, ECS task roles, Lambda execution roles, EKS IRSA (IAM Roles for Service Accounts). Roles provide temporary credentials rotated automatically by the AWS SDK.
- **For external workloads → use IAM Roles Anywhere** (certificate-based) or **OIDC identity federation** (GitHub Actions, GCP, Azure). Eliminate long-lived IAM access keys for CI/CD.
- Write IAM policies with explicit `Allow` statements for specific actions on specific resources. **Never use `Action: *` or `Resource: *` in production policies.** Use IAM Access Analyzer to validate policies. Use Service Control Policies (SCPs) at the org level for guardrails.
- Enable **CloudTrail** for all regions and all account activity. Deliver logs to a centralized S3 bucket in a dedicated security account with immutable retention.
- Use **AWS Secrets Manager** or **Systems Manager Parameter Store (SecureString)** for application secrets. Enable automatic rotation where supported.

### GCP IAM

- **Use attached service accounts** for GCP-hosted workloads (Compute Engine, Cloud Run, GKE Workload Identity, Cloud Functions). The metadata server provides credentials automatically. **Never export service account keys as JSON files for GCP-hosted workloads.**
- **For external workloads → use Workload Identity Federation** with OIDC or SAML providers.
- When service account keys are unavoidable, treat them as critical secrets: store in a secret manager, restrict access, **rotate on a 90-day schedule**, monitor usage via Cloud Audit Logs, alert on key creation.
- Apply IAM roles at the most specific resource level. Use predefined roles over basic roles (Owner, Editor, Viewer). Use IAM Recommender to remove unused permissions.
- Use **GCP Secret Manager** with appropriate replication policies. Access via SDK at runtime with IAM-controlled per-secret permissions.

### Cross-Cloud and Hybrid

- **Use OIDC federation for cross-cloud authentication wherever possible.** AWS-to-Azure, GCP-to-AWS, Azure-to-GCP, and CI/CD-to-any-cloud all support OIDC token exchange. Eliminates static credentials stored externally.
- **For on-premises to cloud** — federate the on-premises IdP (Active Directory, LDAP) with the cloud IAM layer (Azure AD Connect, AWS SSO + SAML, Google Cloud Directory Sync). Users authenticate once against the on-prem IdP and receive cloud-scoped tokens.

---
[Back to Overview](./OVERVIEW.md)
