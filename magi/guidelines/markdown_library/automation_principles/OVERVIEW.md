# Automation Principles and Self-Healing Systems Library

This directory contains an expanded, modularized version of the Automation Principles and Self-Healing Systems guidelines. These principles apply universally to all automation code across the organization — deployment scripts, build pipelines, environment provisioning, scheduled tasks, monitoring configuration, and any repeatable operation that humans currently perform manually. The technology stack is irrelevant; the discipline is the constant.

## Critical Mandates (Read First)
- **The Golden Rule** — If you have to run a manual command to make automation work, that command belongs IN the automation.
- **Self-Sufficiency** — Every script runs to completion on a fresh system without manual intervention.
- **Failure Isolation** — Individual component failures do not cascade.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md) — Self-sufficiency, deterministic execution, failure isolation, operational transparency, minimal footprint; Golden Rule; cost of manual intervention.
2. [Self-Healing Architecture](./SELF_HEALING_ARCHITECTURE.md) — Detect/correct/verify; graceful degradation; the self-healing loop; check-then-act idempotency.
3. [Dependency Resolution](./DEPENDENCY_RESOLUTION.md) — Categories, detection, install, verification, documentation.
4. [Environment Detection and Adaptation](./ENVIRONMENT_DETECTION.md) — OS, distro, privilege, container, CI, architecture; defaults.
5. [Configuration Management](./CONFIGURATION_MANAGEMENT.md) — Sources/precedence, env vars, files, validation, templating, change detection.
6. [Error Handling and Recovery](./ERROR_HANDLING.md) — Classification, context, cleanup, exit codes.
7. [Retry Strategies and Circuit Breakers](./RETRY_CIRCUIT_BREAKERS.md) — Exponential backoff, jitter, circuit breaker.
8. [Health Checks](./HEALTH_CHECKS.md) — Startup, liveness, readiness.
9. [Logging and Observability](./LOGGING_OBSERVABILITY.md) — Levels, structure, structured logging, sensitive data, correlation, progress.
10. [Secret and Credential Management](./SECRET_CREDENTIAL.md) — Sources, handling rules, SSH/remote access, rotation.
11. [Network and Connectivity](./NETWORK_CONNECTIVITY.md) — Verification, DNS, HTTP, downloads, proxy.
12. [File System Operations](./FILE_SYSTEM_OPERATIONS.md) — Directories, files, safe update, temp files, paths.
13. [Process and Service Management](./PROCESS_SERVICE_MANAGEMENT.md) — Lifecycle, service managers, background processes, signal handling.
14. [State Management and Idempotency](./STATE_IDEMPOTENCY.md) — Principles, persistence, atomic transitions, locks, checkpoints.
15. [Deployment Automation Patterns](./DEPLOYMENT_PATTERNS.md) — Blue-green, canary, rolling.
16. [Rollback Strategies](./ROLLBACK_STRATEGIES.md) — Triggers, deploy-with-rollback, database rollback.
17. [Feature Flag Integration](./FEATURE_FLAGS.md) — Cached check, percentage rollout.
18. [Secret Rotation Automation](./SECRET_ROTATION.md) — Single-secret automation, dual-secret zero-downtime.
19. [Scheduled Task Patterns](./SCHEDULED_TASK_PATTERNS.md) — Cron-safe locking, jitter, monitoring.
20. [Testing and Validation](./TESTING_VALIDATION.md) — Categories, isolation, fresh-system, failure injection, assertions.
21. [Shakedown](./SHAKEDOWN.md) — Mandate, surfaces, triggers, execution, classification, artifacts, anti-patterns.
22. [CI/CD Integration](./CICD_INTEGRATION.md) — Pipeline compatibility, artifacts, env vars, parallel execution.
23. [Cross-Platform Considerations](./CROSS_PLATFORM.md) — Shells, tools, paths, package managers.
24. [Defense in Depth](./DEFENSE_IN_DEPTH.md) — Independent layers, Rule of Three.
25. [Prohibited Practices](./PROHIBITED_PRACTICES.md) — Never Do / Always Do lists.
26. [Style Summary](./STYLE_SUMMARY.md) — Quick-reference table for required styles.
