# Application Dockerization Library

This directory contains an expanded, modularized version of the Application Dockerization Guide. It defines the principles, methodology, and complete instructions for containerizing existing applications. The focus is not on Docker mechanics or Kubernetes orchestration—those are covered elsewhere—but on the architectural thinking, decision frameworks, and implementation patterns that produce production-ready containerized applications.

## Critical Mandates (Read First)
- **The Container Is the Deployment Unit** — image is the complete, self-contained deployment artifact.
- **Configuration Lives Outside the Container** — image is immutable; only configuration differs across environments.
- **Containers Are Ephemeral** — start fast, shut down gracefully, no local state survives restart.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md) — Immutability, explicit dependencies, environment parity, isolation, operational readiness.
2. [Containerization Assessment](./CONTAINERIZATION_ASSESSMENT.md) — Architecture analysis, component isolation, database/queue/cache decisions.
3. [Dockerfile Engineering](./DOCKERFILE_ENGINEERING.md) — Base image selection, multi-stage builds, best practices, environment configuration.
4. [.NET Version Migration](./DOTNET_VERSION_MIGRATION.md) — Version landscape, .NET 6→8 and 8→9 migrations, Native AOT, verification.
5. [Application Modifications](./APPLICATION_MODIFICATIONS.md) — Logging, health endpoints, graceful shutdown, config management, DB connections, distributed caching, sessions.
6. [Container Composition](./CONTAINER_COMPOSITION.md) — Docker Compose, dependency management, network configuration.
7. [Build and Deployment Pipeline](./BUILD_DEPLOYMENT_PIPELINE.md) — CI/CD integration, tagging strategy, scanning, registry management.
8. [Operational Concerns](./OPERATIONAL_CONCERNS.md) — Resource limits, observability, security hardening, troubleshooting, sidecar patterns.
9. [Anti-Patterns and Prohibited Practices](./ANTI_PATTERNS.md) — Image, application, operational, and networking anti-patterns.
10. [Migration Patterns](./MIGRATION_PATTERNS.md) — Strangler fig, parallel run, database migration, testing migration.
11. [Reference](./REFERENCE.md) — Checklists, migration reference, ports, sizing, style summary.
