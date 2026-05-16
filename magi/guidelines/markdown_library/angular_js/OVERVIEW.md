# AngularJS (1.x) Development Guidelines Library

This directory contains an expanded, modularized version of the AngularJS Development Guidelines. These guidelines are calibrated to stabilize existing AngularJS workloads and reduce the cost of migration to modern frameworks.

## **CRITICAL DEPRECATION NOTICE**
**AngularJS reached end-of-life in January 2022.** No security patches, no bug fixes, and no compatibility updates are provided. **Active migration to modern Angular, React, or Vue is mandatory for all production systems.**

## Core Mandates
- **Maintenance Mode**: Fix defects, close security holes, or restructure for migration—do not extend the legacy surface area.
- **Component-First**: Use the 1.5+ `.component()` API for all view logic.
- **Minification Safety**: Mandatory `$inject` annotation for all dependencies.
- **Unidirectional Data Flow**: Data down via `<`; events up via `&`.
- **Digest Cycle Vigilance**: Minimize watcher counts and avoid deep watches.

## Table of Contents

1.  [Core Principles](./CORE_PRINCIPLES.md) - Philosophical foundations for legacy maintenance.
2.  [Project Structure](./PROJECT_STRUCTURE.md) - Organization by feature and naming conventions.
3.  [Module System](./MODULE_SYSTEM.md) - Configuration phases and dependency management.
4.  [Dependency Injection](./DEPENDENCY_INJECTION.md) - Minification safety and strict DI.
5.  [Controllers](./CONTROLLERS.md) - `controllerAs` syntax and coordination logic.
6.  [Services, Factories, and Providers](./SERVICES_FACTORIES_PROVIDERS.md) - Singleton design and shared state.
7.  [Directives](./DIRECTIVES.md) - Behavioral extensions and link functions.
8.  [Components (1.5+)](./COMPONENTS.md) - Binding types and lifecycle hooks.
9.  [Scope and Digest Cycle](./SCOPE_MANAGEMENT_DIGEST.md) - Change detection and performance cliffs.
10. [Routing and Navigation](./ROUTING_NAVIGATION.md) - `ui-router` states and resolves.
11. [Forms and Validation](./FORMS_VALIDATION.md) - Named forms and custom validators.
12. [HTTP and API Integration](./HTTP_API_INTEGRATION.md) - Interceptors and promise handling.
13. [Filters](./FILTERS.md) - Formatting transformations and performance.
14. [Performance Optimization](./PERFORMANCE_OPTIMIZATION.md) - Watcher budgets and production settings.
15. [Error Handling](./ERROR_HANDLING.md) - Promise rejections and loading states.
16. [Security Practices](./SECURITY_PRACTICES.md) - SCE, XSS prevention, and dependency pinning.
17. [Testing Strategy](./TESTING_STRATEGY.md) - Karma/Jasmine and mocking patterns.
18. [Shakedown](./SHAKEDOWN.md) - Integration validation for legacy bundles.
19. [Migration Path](./MIGRATION_PATH.md) - Preparing for and executing the move to modern Angular.
20. [Defense in Depth](./DEFENSE_IN_DEPTH.md) - Independent layers of verification.
21. [Prohibited Practices](./PROHIBITED_PRACTICES.md) - The absolute "Never Do" list.
22. [Style Summary](./STYLE_SUMMARY.md) - Quick reference for style requirements.
