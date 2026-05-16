# Bicep and Infrastructure as Code Library

This directory contains an expanded, modularized version of the Bicep and Infrastructure as Code Guidelines. Apply universally to all Bicep files and Infrastructure as Code across the organization.

## Critical Mandates (Read First)
- **Infrastructure Is Code** — Bicep files are source code with the same rigor as application code.
- **Explicit Over Implicit** — every configuration value has a documented source; no reliance on Azure defaults.
- **Azure is the State** — Bicep has no state file; what-if comparisons diff against live infrastructure.

## Table of Contents

1. [IaC Tool Comparison: Bicep vs Alternatives](./IAC_TOOL_COMPARISON.md) — Bicep, Terraform, ARM, Pulumi tradeoffs and decision framework.
2. [Core Principles](./CORE_PRINCIPLES.md) — Declarative intent, idempotency, modularity, compile-time safety, least privilege.
3. [File Organization and Structure](./FILE_ORGANIZATION.md) — Directory layout, file naming, single responsibility, bicepconfig.json.
4. [Naming Conventions](./NAMING_CONVENTIONS.md) — Resource naming, Bicep identifiers, resource-type abbreviations.
5. [Parameters and Variables](./PARAMETERS_VARIABLES.md) — Design, decorators, parameter files, variables, secure parameters.
6. [Modules](./MODULES.md) — Purpose, composition, interface design, registry, versioning.
7. [Resource Definitions](./RESOURCE_DEFINITIONS.md) — Declaration structure, API versions, properties, child resources, existing.
8. [Dependencies and Ordering](./DEPENDENCIES_ORDERING.md) — Implicit, explicit, sequencing, circular dependencies.
9. [Outputs](./OUTPUTS.md) — Purpose, design, chaining, secure, aggregation.
10. [Conditional Deployments](./CONDITIONAL_DEPLOYMENTS.md) — Resources, modules, ternary, null-coalescing.
11. [Loops and Iterations](./LOOPS_ITERATIONS.md) — Resource, index-based, filtered, module, multi-region, nested.
12. [Type System and User-Defined Types](./TYPE_SYSTEM.md) — Built-in types, annotations, user-defined, discriminated unions.
13. [Functions and Expressions](./FUNCTIONS_EXPRESSIONS.md) — Built-in, resource, interpolation, user-defined.
14. [Deployment Scopes](./DEPLOYMENT_SCOPES.md) — Hierarchy, targeting, cross-scope, extension resources.
15. [Testing and Validation](./TESTING_VALIDATION.md) — Compilation, linting, what-if, ARM-TTK, PSRule, integration testing.
16. [Deployment Stacks](./DEPLOYMENT_STACKS.md) — Creation with deny settings, action on unmanage, updates with what-if.
17. [CI/CD Integration](./CICD_INTEGRATION.md) — Azure DevOps, GitHub Actions, deployment names, approvals, rollback.
18. [Security and Secrets Management](./SECURITY_SECRETS.md) — Secret parameters, Key Vault, managed identity, deployment identity, network.
19. [Post-Deployment Shakedown](./SHAKEDOWN.md) — Triggers, validation surfaces, execution, classification, artifacts, anti-patterns.
20. [Defense in Depth](./DEFENSE_IN_DEPTH.md) — Independent layers, Rule of Three.
21. [Prohibited Practices](./PROHIBITED_PRACTICES.md) — Never Do / Always Do lists.
22. [Style Summary](./STYLE_SUMMARY.md) — Quick-reference table for required styles.
