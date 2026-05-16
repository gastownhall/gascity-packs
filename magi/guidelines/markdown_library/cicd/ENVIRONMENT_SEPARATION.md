# Environment Separation

Environment separation isolates development, staging, and production workloads to prevent cross-environment contamination, accidental production deployments, and secrets leakage. **The pipeline enforces environment boundaries — human discipline alone is insufficient.**

### Minimum Three Environments

| Environment | Lifecycle | Purpose |
|:------------|:----------|:--------|
| Development | Ephemeral, per-PR or per-branch | Feature development, preview |
| Staging | Persistent, production-mirror | Pre-production validation |
| Production | Persistent | Live workloads |

Each environment has its own configuration, secrets, database instances, API endpoints, and DNS. **No environment shares credentials with another.**

### Branch-to-Environment Mapping

Pipeline deployment targets are determined by branch/tag, not by manual environment selection in pipeline configuration:
- Push to `main` → automatically deploys to staging
- Tag creation → deploys to production after approval gates
- Feature branches → deploy to ephemeral preview environments

This mapping is enforced **in the pipeline definition**, not documented in a wiki.

### Production Approval Gates

Production deployments require at least one manual approval gate from a designated approver (team lead, SRE, release manager). Automated deployment to staging is acceptable and encouraged. Automated deployment to production without human verification is acceptable **only** for organizations with mature canary deployment and automated rollback infrastructure.

### Per-Environment Secret Scopes

Secrets for each environment are stored in separate secret scopes:
- GitHub: environment secrets
- GitLab: environment-scoped variables
- Azure DevOps: variable groups per stage
- Vault: separate paths per environment

A pipeline job targeting staging cannot access production secrets. The CI platform's access control enforces this boundary.

### Ephemeral Preview Environments

Preview environments spin up on PR creation and tear down on PR close/merge. Implement automatic cleanup to prevent resource leakage from abandoned PRs.

### Staging-Production Parity

Staging mirrors production configuration as closely as possible:
- Same infrastructure-as-code templates (parameterized for scale)
- Same runtime versions
- Same network topology
- Same third-party service integrations (test accounts)

**Configuration drift between staging and production is the primary cause of "works in staging, fails in production" incidents.**

---
[Back to Overview](./OVERVIEW.md)
