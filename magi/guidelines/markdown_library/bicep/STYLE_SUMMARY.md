# Style Summary

| Element | Required Style |
|:--------|:---------------|
| File Names | `camelCase.bicep` matching primary resource |
| Parameters | `camelCase` with `@description()` decorators |
| Variables | `camelCase` describing computed value |
| Resources | `camelCase` symbolic names matching purpose |
| Modules | `camelCase` matching module file name |
| Outputs | `camelCase` with `@description()`, `@secure()` for secrets |
| API Versions | Latest stable; documented exceptions |
| Naming Convention | `{workload}-{env}-{region}-{type}-{instance}` |
| Secrets | `@secure()` parameters; Key Vault references |
| Dependencies | Implicit via property references; explicit `dependsOn` when required |
| Conditionals | `if` for resources/modules; ternary for properties |
| Loops | `for` with descriptive iteration variables |
| Types | User-defined types for complex parameters |
| Scopes | Explicit `targetScope`; cross-scope with `scope` property |
| Validation | Build, lint, what-if in CI pipeline |
| Deployment | Environment-specific parameter files; deterministic names |
| Stacks | Deny-settings + action-on-unmanage for production |
| Shakedown | Read-only validation against deployed state; ten categories; classified outcome |
| Defense in Depth | Build + lint + what-if + parameter constraints + policy + drift + cost + rollback + shakedown |

---

Following these guidelines produces Bicep infrastructure code that is type-safe, maintainable, secure, and production-ready. The compilation step catches errors before deployment. The declarative model ensures idempotent operations. The module system enables reuse without complexity explosion. The shakedown layer ensures the deployed state matches declared intent.

**Apply this guidance universally to all Bicep files and Infrastructure as Code across the organization.**

---
[Back to Overview](./OVERVIEW.md)
