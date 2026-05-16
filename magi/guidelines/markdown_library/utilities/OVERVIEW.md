# .utilities Suite Library

The `.utilities` suite is a self-contained, portable automation framework designed for enterprise development workflows. It provides standardized tooling for testing, deployment, error analysis, and local development across multiple language ecosystems. These guidelines govern the architecture, usage patterns, and extension of the suite.

## Critical Mandates (Read First)

- **Absolute Portability** — The suite functions identically across any project without modification; no project-specific values exist within `.utilities/`.
- **Self-Healing Dependencies** — Missing tools trigger automatic installation via platform-appropriate package managers; scripts never fail due to absent prerequisites without attempting remediation.
- **Centralized Logging** — All operations produce structured logs in `.utilities/_logs/` for debugging, auditing, integration with external monitoring systems.
- **Modular Composition** — Each script sources only required helpers from `.common/`; no monolithic imports or circular dependencies.
- **Environment-Driven Configuration** — Runtime behavior derives from `.env` files and environment variables; hardcoded values are prohibited.
- **Shakedown Required** — Every state-mutating utility MUST expose `--shakedown` mode or a companion `shakedown.sh`; utilities without one are prohibited.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [Architecture Overview](./ARCHITECTURE.md)
3. [Module Organization](./MODULE_ORGANIZATION.md)
4. [Common Module Framework](./COMMON_FRAMEWORK.md)
5. [Environment and Configuration](./ENVIRONMENT.md)
6. [Backend Testing Infrastructure](./BACKEND_TESTING.md)
7. [Docker Operations Module](./DOCKER_OPERATIONS.md)
8. [Error Handling Framework](./ERROR_HANDLING.md)
9. [Frontend Evaluation Tools](./FRONTEND_TOOLS.md)
10. [Local Azure Services](./LOCAL_AZURE.md)
11. [External Tool Integration](./EXTERNAL_TOOLS.md)
12. [Logging Infrastructure](./LOGGING.md)
13. [Cross-Platform Compatibility](./CROSS_PLATFORM.md)
14. [Symlink Management](./SYMLINKS.md)
15. [Color-Coded Output Standards](./COLOR_OUTPUT.md)
16. [Cross-Project Compatibility](./CROSS_PROJECT.md)
17. [Dependency Management](./DEPENDENCIES.md)
18. [Portability Requirements](./PORTABILITY.md)
19. [Shakedown — Integration Validation](./SHAKEDOWN.md)
20. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
21. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
22. [Required Practices](./REQUIRED_PRACTICES.md)
23. [Style Summary](./STYLE_SUMMARY.md)
