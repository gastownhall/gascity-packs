# Core Principles

These guidelines define strict, maintainable, and secure patterns for Bicep-based Infrastructure as Code, optimizing for:

- **Declarative Intent**: Infrastructure definitions describe desired end state, not procedural steps. The deployment engine determines how to achieve that state.
- **Idempotency**: Deploying the same template multiple times produces identical results. No side effects from repeated execution.
- **Modularity**: Complex infrastructure decomposes into reusable, testable, independently deployable modules.
- **Compile-Time Safety**: Errors surface during authoring and compilation, not during deployment. Type checking, linting, and validation run before any Azure API call.
- **Least Privilege**: Templates request only necessary permissions. Secrets never appear in source control or deployment logs.

### Primary Rule: Infrastructure Is Code

Bicep files are source code. They receive the same rigor as application code: version control, code review, automated testing, and continuous deployment. Ad-hoc portal changes that bypass IaC create configuration drift that compounds into operational risk.

### Secondary Rule: Explicit Over Implicit

Every configuration value has a documented source: parameter, variable, or resource property. No reliance on Azure defaults that might change between API versions. If a property matters to your deployment, set it explicitly.

### Deployment Philosophy

Bicep templates are compiled to ARM and submitted to Azure Resource Manager. ARM handles:
- Dependency resolution and parallel deployment
- Idempotent resource creation and updates
- Rollback on failure (when configured)
- State tracking via Azure itself

This architecture means Bicep has no state file. **Azure is the state.** What-if comparisons diff against live infrastructure, not a local state representation.

---
[Back to Overview](./OVERVIEW.md)
