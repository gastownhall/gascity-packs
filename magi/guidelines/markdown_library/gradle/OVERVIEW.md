# Gradle Build System Library

These guidelines define strict conventions for Gradle 8.5+ build configuration, dependency management, task architecture, build caching, multi-project builds, plugin development, CI/CD integration, and reproducible build discipline across all JVM projects.

## Critical Mandates (Read First)
- **Kotlin DSL by Default** — all new projects use `build.gradle.kts` exclusively.
- **Configuration Avoidance** — `tasks.register` and `tasks.named` only; never `tasks.create` / `tasks.getByName`.
- **Reproducible Builds** — version catalogs + dependency locking + toolchains; no inline versions.
- **Build Cache First** — configuration cache and build cache enabled; tasks declare inputs and outputs.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [Project Structure](./PROJECT_STRUCTURE.md)
3. [Build Script Configuration](./BUILD_SCRIPT_CONFIGURATION.md)
4. [Dependency Management](./DEPENDENCY_MANAGEMENT.md)
5. [Plugin Architecture](./PLUGIN_ARCHITECTURE.md)
6. [Task Configuration](./TASK_CONFIGURATION.md)
7. [Multi-Project Builds](./MULTI_PROJECT_BUILDS.md)
8. [Build Caching](./BUILD_CACHING.md)
9. [Configuration Cache](./CONFIGURATION_CACHE.md)
10. [Toolchains](./TOOLCHAINS.md)
11. [Testing](./TESTING.md)
12. [Shakedown — Packaged Artifact Validation](./SHAKEDOWN.md)
13. [Publishing](./PUBLISHING.md)
14. [Custom Plugin Development](./CUSTOM_PLUGIN_DEVELOPMENT.md)
15. [CI/CD Integration](./CICD_INTEGRATION.md)
16. [Build Scans and Debugging](./BUILD_SCANS_DEBUGGING.md)
17. [Security](./SECURITY.md)
18. [Migration](./MIGRATION.md)
19. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
20. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
21. [Required Practices](./REQUIRED_PRACTICES.md)
22. [Style Summary](./STYLE_SUMMARY.md)
