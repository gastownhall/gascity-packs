# Docker Guidelines Library

This directory contains an expanded, modularized version of the Docker Guidelines. Apply universally to all Dockerfiles and container configurations across the organization.

## Critical Mandates (Read First)
- **Images Are Immutable Artifacts** — once built and tagged, never changes. Configuration varies via env vars, mounted secrets, orchestration.
- **Smallest Possible Image** — every megabyte increases pull time, storage cost, attack surface.
- **Build vs Runtime Separation** — build tools never appear in runtime images; multi-stage builds enforce this architecturally.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md) — Immutability, minimal attack surface, reproducibility, container as deployment unit, externalized config.
2. [Base Image Selection](./BASE_IMAGE_SELECTION.md) — Selection criteria, provenance, hierarchy, distroless, version pinning.
3. [Dockerfile Structure and Syntax](./DOCKERFILE_STRUCTURE.md) — Instruction ordering, syntax standards, exec form, COPY vs ADD.
4. [Layer Optimization](./LAYER_OPTIMIZATION.md) — Layer fundamentals, minimizing count, cache optimization, cleanup, analysis.
5. [Multi-Stage Builds](./MULTI_STAGE_BUILDS.md) — Purpose, standard pattern, naming, target selection, dependency caching, parallel stages, cross-compilation.
6. [BuildKit Features](./BUILDKIT_FEATURES.md) — Syntax, cache mounts, heredoc, COPY --link, bind mounts, SSH mounts.
7. [Build Context and Ignore Patterns](./BUILD_CONTEXT.md) — Context fundamentals, .dockerignore, minimization, secret handling.
8. [Security Hardening](./SECURITY_HARDENING.md) — Non-root, filesystem permissions, read-only root, capability dropping, security options.
9. [Security Scanning and Supply Chain](./SECURITY_SCANNING.md) — Vulnerability scanning, SBOM, image signing.
10. [Secret Management](./SECRET_MANAGEMENT.md) — Build-time secrets, runtime secrets, rotation.
11. [Runtime Configuration](./RUNTIME_CONFIGURATION.md) — Environment variables, config mounting, ENTRYPOINT vs CMD, signal handling, init.
12. [Networking](./NETWORKING.md) — Network modes, port exposure, service discovery, custom networks, isolation.
13. [Volume and Storage Management](./VOLUME_STORAGE.md) — Volume types, named volumes, bind mounts, tmpfs, permissions, backup.
14. [Health Checks and Lifecycle](./HEALTH_LIFECYCLE.md) — Configuration, commands, dependencies, endpoint types, graceful shutdown, hooks.
15. [Compose Configuration](./COMPOSE_CONFIGURATION.md) — File structure, service definition, profiles, environment, dependencies.
16. [Registry and Distribution](./REGISTRY_DISTRIBUTION.md) — Tagging, authentication, push/pull, retention.
17. [Logging and Observability](./LOGGING_OBSERVABILITY.md) — Strategy, drivers, format, metrics, tracing.
18. [Resource Constraints](./RESOURCE_CONSTRAINTS.md) — Memory/CPU limits, sizing guidelines.
19. [Performance Optimization](./PERFORMANCE_OPTIMIZATION.md) — Startup, image size reduction techniques.
20. [Container Orchestration](./CONTAINER_ORCHESTRATION.md) — Kubernetes probe mapping, init containers.
21. [CI/CD Integration](./CICD_INTEGRATION.md) — Automated builds, tagging strategy.
22. [Container Testing](./CONTAINER_TESTING.md) — Integration tests, Testcontainers.
23. [Container Shakedown](./SHAKEDOWN.md) — Definition, triggers, validation categories, execution, classification, anti-patterns.
24. [Defense in Depth](./DEFENSE_IN_DEPTH.md) — Independent layers, Rule of Three.
25. [Development vs Production](./DEV_VS_PROD.md) — Configuration differences, layering.
26. [Migration to Containers](./MIGRATION.md) — Readiness assessment, strangler fig pattern.
27. [Troubleshooting](./TROUBLESHOOTING.md) — Debug commands, exit codes.
28. [Prohibited Practices](./PROHIBITED_PRACTICES.md) — Never Do list.
29. [Required Practices](./REQUIRED_PRACTICES.md) — Always Do list.
30. [Style Summary](./STYLE_SUMMARY.md) — Quick-reference table for required styles.
