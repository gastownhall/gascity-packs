# Azure Configuration and Secrets Management Library

This directory contains an expanded, modularized version of the Azure Configuration and Secrets Management Guidelines. Apply universally to all Azure App Configuration, Key Vault, and infrastructure parameter implementations across the organization.

## Critical Mandates (Read First)
- **Secrets and Configuration Are Different Things** — Key Vault for secrets, App Configuration for non-sensitive settings.
- **Configuration Is Not Deployment** — change configuration without redeploying.
- **Sentinel is not optional for production** — it transforms audit logs into actionable security intelligence.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md) — Separation of concerns, zero secrets in code, centralized config, least privilege, auditability.
2. [Resource Naming Conventions](./RESOURCE_NAMING.md) — Format and per-resource abbreviations, lengths, charsets.
3. [Tagging Strategy](./TAGGING_STRATEGY.md) — Required tags and policy-enforced governance.
4. [App Configuration Fundamentals](./APP_CONFIG_FUNDAMENTALS.md) — Service purpose, tier, key naming, labels, content types, snapshots.
5. [Key Vault Fundamentals](./KEY_VAULT_FUNDAMENTALS.md) — Service purpose, vault types, lifecycle, naming, certificates, keys.
6. [Hierarchical Configuration Design](./HIERARCHICAL_CONFIG.md) — Layering precedence, Key Vault references, configuration composition.
7. [Feature Flags and Dynamic Configuration](./FEATURE_FLAGS.md) — Architecture, naming, targeting filters, refresh, lifecycle.
8. [Secret Management Patterns](./SECRET_MANAGEMENT.md) — Rotation schedule and process, connection string patterns.
9. [Managed Identity Patterns](./MANAGED_IDENTITY.md) — System vs user-assigned, authentication priority, DefaultAzureCredential chain.
10. [Access Control and Identity](./ACCESS_CONTROL.md) — RBAC roles, access policies vs RBAC, service principals, network security.
11. [ARM/Bicep Parameter Patterns](./ARM_BICEP_PARAMETERS.md) — Bicep parameter files, naming, secure decorator, KV integration.
12. [Sentinel Integration and Monitoring](./SENTINEL_INTEGRATION.md) — Diagnostic settings, analytics rules, KQL, workbooks, alerting.
13. [SDK Usage Patterns](./SDK_USAGE.md) — App Configuration and Key Vault SDKs, error handling.
14. [Multi-Environment Strategy](./MULTI_ENVIRONMENT.md) — Topology options, recommended topology, configuration promotion.
15. [Disaster Recovery and Backup](./DR_BACKUP.md) — Geo-replication, redundancy, backup, recovery procedures.
16. [Cost Optimization](./COST_OPTIMIZATION.md) — Quotas, App Config and Key Vault cost drivers.
17. [Compliance and Governance](./COMPLIANCE_GOVERNANCE.md) — Certifications, audit requirements.
18. [Variable-Restructure Shakedown](./VARIABLE_RESTRUCTURE_SHAKEDOWN.md) — Definition, triggers, validation checks, execution, classification.
19. [Defense in Depth](./DEFENSE_IN_DEPTH.md) — Independent layers, Rule of Three.
20. [Prohibited Practices](./PROHIBITED_PRACTICES.md) — Never Do / Always Do lists.
21. [Style Summary](./STYLE_SUMMARY.md) — Quick-reference table for required styles.
