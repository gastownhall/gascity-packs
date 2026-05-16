# CI/CD Pipeline Guidelines Library

This directory contains an expanded, modularized version of the CI/CD Pipeline Guidelines. Mandatory for all automated build, test, and deployment pipelines regardless of platform — GitHub Actions, GitLab CI, Azure DevOps, Jenkins, Gitea Actions, CircleCI, Buildkite, Drone, ArgoCD, Tekton, or any other CI/CD system. Principles are universal; platform-specific implementation details are noted where they diverge. Targets SLSA Build Level 2+, Sigstore/Cosign signing, OCI registries, SBOM generation via Syft/Trivy, OpenSSF Scorecard compliance.

## Critical Mandates (Read First)
- **Pipeline Definitions Live in the Repository** — no pipeline logic exists solely in CI platform UI configuration.
- **Every Run Is Traceable to a Commit** — traceability is non-negotiable.
- **Pipeline Is Code** — version-controlled, reviewed, tested with the same rigor as application code.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md) — Pipeline is code, hermetic builds, immutable artifacts, shift left, zero trust.
2. [Workflow Structure and Organization](./WORKFLOW_STRUCTURE.md) — Sequential stage gates, parallelism, templates, triggers, filtering, timeouts, concurrency.
3. [Source Control and Branch Strategy](./SOURCE_CONTROL_BRANCH.md) — Protected main, signed commits, short-lived branches, version tags, changelogs.
4. [Environment Separation](./ENVIRONMENT_SEPARATION.md) — Three environments, branch mapping, approval gates, secrets, preview, parity.
5. [Secrets Management in Pipelines](./SECRETS_MANAGEMENT.md) — Storage, masking, scope, OIDC federation, fork PR secrets, rotation, audit.
6. [Build Reproducibility and Determinism](./BUILD_REPRODUCIBILITY.md) — Pin versions, lockfiles, SHA-pinned actions, metadata, isolation.
7. [Pipeline Shakedown Stage](./SHAKEDOWN_STAGE.md) — Definition, placement, triggers, environment, assertions, classification, anti-patterns.
8. [Testing Strategy in CI](./TESTING_STRATEGY.md) — Unit, integration, E2E, format, flaky tests, coverage.
9. [Static Analysis and Code Quality](./STATIC_ANALYSIS.md) — Linters, formatters, SAST, type checking, IaC linting.
10. [Dependency Management and Supply Chain Security](./DEPENDENCY_SUPPLY_CHAIN.md) — Vuln scanning, pinning, hash verification, SBOM, Scorecard, dependency confusion.
11. [Container Image Security](./CONTAINER_IMAGE_SECURITY.md) — Minimal base, scanning, digest pinning, secrets, non-root, OCI annotations.
12. [Artifact Signing and Provenance](./ARTIFACT_SIGNING.md) — Sigstore Cosign, sign by digest, verify, SLSA provenance, SBOM attestations.
13. [Deployment Strategies and Gating](./DEPLOYMENT_STRATEGIES.md) — Production gates, approval, progressive strategies, smoke tests, windows, promote.
14. [Rollback and Recovery](./ROLLBACK_RECOVERY.md) — Reversibility, retention, testing, migrations, automated triggers.
15. [Runner and Agent Security](./RUNNER_SECURITY.md) — Ephemeral runners, trust isolation, container/VM isolation, updates, monitoring.
16. [Caching Strategy](./CACHING_STRATEGY.md) — Dependency caching, Docker layers, never cache secrets, TTLs.
17. [Infrastructure as Code in CI/CD](./IAC_IN_CICD.md) — Plan on PR, pipeline-only apply, remote state, drift detection.
18. [Monitoring, Observability, and Feedback](./MONITORING_OBSERVABILITY.md) — Pipeline metrics, alerts, DORA metrics, post-deploy monitoring.
19. [Notifications and Communication](./NOTIFICATIONS_COMMUNICATION.md) — Notify on failure/recovery, actionable context.
20. [Compliance and Audit](./COMPLIANCE_AUDIT.md) — Log retention, separation of duties, deployment audit, pipeline definition protection.
21. [Pipeline Performance and Cost](./PERFORMANCE_COST.md) — Duration targets, runner sizing, resource cleanup.
22. [Defense in Depth](./DEFENSE_IN_DEPTH.md) — Independent layers, Rule of Three.
23. [Prohibited Practices](./PROHIBITED_PRACTICES.md) — Never Do / Always Do lists.
24. [Style Summary](./STYLE_SUMMARY.md) — Quick-reference table for required styles.
