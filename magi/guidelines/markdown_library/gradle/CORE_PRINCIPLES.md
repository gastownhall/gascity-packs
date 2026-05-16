# Core Principles

These guidelines define strict conventions for Gradle 8.5+ build configuration, dependency management, task architecture, build caching, multi-project builds, plugin development, CI/CD integration, and reproducible build discipline across all JVM projects.

**Runtime:** Gradle 8.5+, JDK 17+ (build JVM), Kotlin DSL 1.9+, configuration cache enabled.

### Kotlin DSL by Default

All new projects use Kotlin DSL (`build.gradle.kts`) exclusively. Kotlin DSL provides compile-time type safety, IDE auto-completion, and refactoring support that Groovy cannot match. Existing Groovy builds migrate to Kotlin DSL during major version upgrades or significant build refactoring. Mixing DSLs within a single multi-project build is prohibited for new projects.

### Configuration Avoidance

Tasks configure lazily through the `tasks.register` API. Eager configuration with `tasks.create` wastes build time on tasks that never execute. Every task registration uses the lazy API. Every task reference uses `tasks.named` instead of `tasks.getByName`. Configuration avoidance is not an optimization — it is a baseline requirement for professional Gradle usage.

### Reproducible Builds

Dependency locking, version catalogs, and explicit version declarations ensure builds produce identical outputs across environments and time. No dependency version is declared inline in build scripts. All versions live in `gradle/libs.versions.toml`. Lock files are committed and validated in CI. A build that works today must work identically next year given the same inputs.

### Build Cache First

Local and remote build caching transforms incremental builds into near-instantaneous operations. Every custom task declares inputs and outputs for cacheability. Cache-defeating patterns (non-deterministic outputs, absolute paths in inputs, missing input annotations) are build defects. CI pushes to remote cache; developer machines pull. Cache hit rate is a key build health metric.

### Convention Over Configuration

Apply sensible defaults through plugins and conventions. Explicit configuration exists only where behavior must deviate from standards. Repeated configuration across subprojects extracts to convention plugins in `buildSrc` or included builds. A subproject build script should contain only its unique requirements — everything else inherits from conventions.

### Golden Rule: Build Performance Is Developer Productivity

Every millisecond of build time multiplies across every developer, every commit, and every CI run. A 10-second build that could be 2 seconds costs hundreds of developer-hours annually on a mid-sized team.

Configuration avoidance, task output caching, incremental compilation, and parallel execution are baseline requirements. Builds that defeat these mechanisms through eager configuration, non-cacheable tasks, or serialized execution are technical debt with compound interest.

### Explicit Dependencies

Gradle's dependency resolution operates on declared dependencies, not filesystem state or implicit classpath inheritance. Every dependency a project consumes must be explicitly declared with the correct configuration scope. Projects that work "by accident" through transitive exposure fail unpredictably when dependency graphs shift. **Declare what you use; use what you declare.**

---
[Back to Overview](./OVERVIEW.md)
