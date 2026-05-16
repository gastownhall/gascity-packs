# Angular Development Guidelines Library

This directory contains an expanded, modularized version of the Angular Development Guidelines. These guidelines define strict, scalable, and maintainable patterns for modern Angular application development (v17+).

## Core Mandates (Read First)
- **Standalone by Default**: NgModules are for legacy/third-party interop only.
- **Signal-First Reactivity**: Signals for synchronous state; RxJS for asynchronous streams.
- **Strict Type Safety**: TypeScript strict mode and zero `any` types.
- **OnPush Change Detection**: Mandatory for all components.
- **Zoneless Target**: Architectural target is zone-free operation.

## Table of Contents

1.  [Core Principles](./CORE_PRINCIPLES.md) - Philosophical foundations and primary rules.
2.  [Project Architecture](./PROJECT_ARCHITECTURE.md) - Directory structure, layer responsibilities, and lazy loading.
3.  [Component Design](./COMPONENT_DESIGN.md) - Lifecycle, signal-based inputs/outputs, and size constraints.
4.  [Template Patterns](./TEMPLATE_PATTERNS.md) - Built-in control flow, deferred loading, and type checking.
5.  [Dependency Injection](./DEPENDENCY_INJECTION.md) - The `inject()` function and service architecture.
6.  [RxJS Patterns](./RXJS_PATTERNS.md) - Stream orchestration, operators, and subscription management.
7.  [Signals and Reactive State](./SIGNALS_REACTIVE_STATE.md) - Computed signals, effects, and state ownership.
8.  [Routing and Navigation](./ROUTING_NAVIGATION.md) - Functional guards, resolvers, and input binding.
9.  [Forms and Validation](./FORMS_VALIDATION.md) - Typed reactive forms and validation strategies.
10. [HTTP and API Integration](./HTTP_API_INTEGRATION.md) - Functional interceptors, retries, and schema validation.
11. [State Management](./STATE_MANAGEMENT.md) - Component vs. Service vs. Dedicated Store (SignalStore).
12. [Performance Optimization](./PERFORMANCE_OPTIMIZATION.md) - Lazy loading, bundle optimization, and virtual scrolling.
13. [Error Handling and Resilience](./ERROR_HANDLING_RESILIENCE.md) - Global handlers and component-level boundaries.
14. [Security Practices](./SECURITY_PRACTICES.md) - Sanitization, CSP, CSRF, and authentication.
15. [SSR and Hydration](./SSR_HYDRATION.md) - Client hydration and platform-specific code.
16. [Testing Strategy](./TESTING_STRATEGY.md) - Test pyramid, Signal testing, and coverage.
17. [Build and Deployment](./BUILD_DEPLOYMENT.md) - Angular configuration, environments, and CI pipelines.
18. [Shakedown](./SHAKEDOWN.md) - End-to-end production bundle validation.
19. [Migration Paths](./MIGRATION_PATHS.md) - Incremental steps to modern Angular.
20. [Defense in Depth](./DEFENSE_IN_DEPTH.md) - Independent layers of verification.
21. [Prohibited Practices](./PROHIBITED_PRACTICES.md) - The absolute "Never Do" list.
22. [Style Summary](./STYLE_SUMMARY.md) - Quick reference for style requirements.
