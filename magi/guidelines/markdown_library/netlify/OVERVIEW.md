# Netlify Deployment Library

These guidelines define strict, reproducible, and production-grade patterns for all sites and applications deployed to Netlify, optimizing for configuration as code, atomic deploys, edge-first architecture, platform primitives, and Git-driven workflow.

## Critical Mandates (Read First)
- **`netlify.toml` Is the Single Source of Truth** — UI-only configuration creates invisible drift.
- **Deploy Previews Are Mandatory** — every PR generates a preview reflecting exact production output.
- **Atomic Deploys** — every deploy is a complete, immutable snapshot.
- **Pin All Runtime Versions** — unpinned versions are the leading cause of build failures.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [Project Configuration](./PROJECT_CONFIGURATION.md)
3. [Build Pipeline](./BUILD_PIPELINE.md)
4. [Deploy Strategy](./DEPLOY_STRATEGY.md)
5. [Post-Deploy Shakedown](./SHAKEDOWN.md)
6. [Serverless Functions](./SERVERLESS_FUNCTIONS.md)
7. [Edge Functions](./EDGE_FUNCTIONS.md)
8. [Routing — Redirects and Rewrites](./ROUTING.md)
9. [Custom Headers and Security](./HEADERS_SECURITY.md)
10. [Caching Architecture](./CACHING.md)
11. [Data and Storage Primitives](./DATA_STORAGE.md)
12. [Environment Variables and Secrets](./ENVIRONMENT_SECRETS.md)
13. [Image CDN and Asset Optimization](./IMAGE_CDN.md)
14. [Monorepo Configuration](./MONOREPO.md)
15. [Framework Integration](./FRAMEWORK_INTEGRATION.md)
16. [Observability and Debugging](./OBSERVABILITY.md)
17. [Cost Management and Plan Governance](./COST_MANAGEMENT.md)
18. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
19. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
20. [Required Practices](./REQUIRED_PRACTICES.md)
21. [Style Summary](./STYLE_SUMMARY.md)
