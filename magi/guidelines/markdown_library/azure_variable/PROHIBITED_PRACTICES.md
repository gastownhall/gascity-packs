# Prohibited Practices

### Never Do

- Store secrets in App Configuration without Key Vault reference
- Use access policies on new Key Vault deployments; use RBAC exclusively
- Store credentials in source control, environment variables at build time, or application binaries
- Grant Key Vault Contributor role to application identities; they need only Secrets User
- Disable soft delete or purge protection on production Key Vaults
- Use service principal secrets when managed identity is available
- Skip Sentinel integration for production vaults and configuration stores
- Manually copy configuration between environments; use infrastructure as code
- Set feature flags to expire; use explicit cleanup procedures
- Access Key Vault on every application request; cache appropriately
- Use public network access without firewall rules; prefer private endpoints
- Create secrets without expiration dates
- Share Key Vaults across production and non-production environments
- Grant broad access for convenience; scope permissions minimally
- Ignore throttling errors; they indicate design problems
- Run discrete `az` commands at the prompt — wrap in turnkey scripts under `.utilities/.azure/`
- Stack unrelated variable edits into a rename PR
- Run the variable-restructure shakedown against staging or production

### Always Do

- Use managed identity for Azure-hosted workloads
- Enable diagnostic settings streaming to Log Analytics and Sentinel
- Set expiration dates on all secrets
- Use Key Vault references in App Configuration for secret values
- Implement secret rotation automation
- Use private endpoints for production workloads
- Separate production Key Vault from non-production environments
- Review access permissions quarterly; remove unnecessary grants
- Test disaster recovery procedures annually
- Monitor request counts and set alerts for quota thresholds
- Document secret purposes and rotation procedures
- Use labels for environment segregation in App Configuration
- Enable geo-replication for production App Configuration stores
- Implement configuration change review process via pull requests
- Cache configuration and secrets appropriately in applications
- Apply required tags via Azure Policy at the resource group level
- Use `@secure()` decorator on every sensitive Bicep parameter
- Run the variable-restructure shakedown after every trigger condition in §18

---
[Back to Overview](./OVERVIEW.md)
