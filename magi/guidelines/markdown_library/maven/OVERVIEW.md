# Unified Maven Development Library

These guidelines define a strict, readable, and consistent format for all Maven projects, optimizing for maintainability, reproducibility, performance, and clarity.

## Critical Mandates (Read First)
- **Convention Over Configuration** — follow Maven conventions strictly; deviations are documented.
- **No SNAPSHOT in Production** — pin versions; never `LATEST`/`RELEASE`/version ranges.
- **`dependencyManagement` for Versions** — BOM imports for framework dependencies.
- **Reproducible Builds** — `project.build.outputTimestamp` set so artifacts are byte-identical.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [Project Structure and Organization](./PROJECT_STRUCTURE.md)
3. [POM File Configuration](./POM_CONFIGURATION.md)
4. [Dependency Management](./DEPENDENCY_MANAGEMENT.md)
5. [Build Configuration](./BUILD_CONFIGURATION.md)
6. [Multi-Module Projects](./MULTI_MODULE.md)
7. [Plugin Configuration](./PLUGIN_CONFIGURATION.md)
8. [Java 21+ Patterns](./JAVA_21_PATTERNS.md)
9. [Spring Boot Patterns](./SPRING_BOOT.md)
10. [Profile Management](./PROFILE_MANAGEMENT.md)
11. [Resource Handling](./RESOURCE_HANDLING.md)
12. [Testing Configuration](./TESTING.md)
13. [Release Management](./RELEASE_MANAGEMENT.md)
14. [CI/CD Integration](./CICD_INTEGRATION.md)
15. [Deployment and Distribution](./DEPLOYMENT.md)
16. [Property Management](./PROPERTY_MANAGEMENT.md)
17. [Shakedown — Verify-Phase Integration Validation](./SHAKEDOWN.md)
18. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
19. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
20. [Required Practices](./REQUIRED_PRACTICES.md)
21. [Style Summary](./STYLE_SUMMARY.md)
