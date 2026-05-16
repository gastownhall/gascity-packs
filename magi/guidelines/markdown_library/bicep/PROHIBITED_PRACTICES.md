# Prohibited Practices

### Never Do

- Hardcode secrets, connection strings, or passwords in templates
- Use `*` in IP rules or firewall configurations
- Deploy with `--mode Complete` without understanding implications
- Ignore linter warnings; fix them or document exceptions
- Use deprecated API versions without migration plan
- Create circular dependencies between resources
- Store parameter files with secrets in source control
- Deploy directly to production without what-if analysis
- Use non-deterministic deployment names that obscure history
- Skip tagging resources; tags enable cost allocation and governance
- Deploy public endpoints for data services without explicit justification
- Hardcode subscription IDs, tenant IDs, or resource group names
- Use `any()` type to bypass type checking
- Create modules without parameter descriptions
- Output secrets unnecessarily; prefer Key Vault references
- Treat `provisioningState` `Succeeded` as proof of correct wiring
- Skip post-deployment shakedown after triggers in §19
- Mutate resources during shakedown to "fix" missed dependencies

### Always Do

- Use `@secure()` for all sensitive parameters
- Set explicit API versions on all resources
- Configure diagnostic settings for all supported resources
- Apply consistent tagging across all resources
- Use managed identity over shared keys
- Validate templates before deployment
- Review what-if output for unexpected changes
- Document module interfaces with `@description()` decorators
- Use parameter files for environment-specific values
- Enable soft-delete and purge protection on Key Vaults
- Configure network restrictions on all data services
- Use RBAC over access policies where supported
- Maintain deployment history for rollback capability
- Test infrastructure changes in non-production first
- Run post-deployment shakedown after every trigger condition in §19

---
[Back to Overview](./OVERVIEW.md)
