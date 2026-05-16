# Apache Wicket Development Library

**Runtime:** Apache Wicket 9.x / 10.x, Java 11+ (Wicket 9) or Java 17+ (Wicket 10), Jakarta Servlet 5+

Defines strict conventions for Apache Wicket component-based architecture, model system, HTML/Java separation, serialization discipline, session management, security, and server-side state management. Applies to all server-side rendered Java web applications using Apache Wicket — custom components, panels, forms, AJAX interactions, and enterprise deployments with clustering and session replication.

## Critical Mandates (Read First)

- **Component-Oriented Architecture** — Web pages are object hierarchies, not templates with embedded code; think Swing for the web, not MVC request handlers.
- **Server-Side State Management** — Wicket manages page state on the server; non-serializable fields break clustering and back-button navigation.
- **Strict HTML/Java Separation** — HTML templates contain zero logic; the boundary is absolute and templates must be valid HTML previewable in browsers without Wicket processing.
- **Model-Driven Components** — Every component reads/writes data through `IModel` abstractions; passing raw objects creates stale data, serialization bloat, and tight coupling.
- **Type Safety Throughout** — Use generic `IModel<T>` properly; avoid raw types and string-based property access where type-safe alternatives exist.
- **Components Own Their Markup** — Every Wicket component binds to exactly one HTML element via `wicket:id`.
- **Models Are Not Optional** — Every component that displays or edits data uses an `IModel`, never raw object references.
- **Shakedown Required** — Page-flow shakedown against a real servlet container after every triggering change.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [Project Structure](./PROJECT_STRUCTURE.md)
3. [Component Architecture](./COMPONENT_ARCHITECTURE.md)
4. [Model System](./MODEL_SYSTEM.md)
5. [HTML Markup](./HTML_MARKUP.md)
6. [Forms and Validation](./FORMS.md)
7. [AJAX and Behaviors](./AJAX.md)
8. [Session and State](./SESSION_STATE.md)
9. [Serialization](./SERIALIZATION.md)
10. [Security](./SECURITY.md)
11. [Resources](./RESOURCES.md)
12. [Internationalization](./I18N.md)
13. [Testing](./TESTING.md)
14. [Page-Flow Shakedown](./SHAKEDOWN.md)
15. [Performance](./PERFORMANCE.md)
16. [Dependency Injection](./DI.md)
17. [Deployment](./DEPLOYMENT.md)
18. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
19. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
20. [Required Practices](./REQUIRED_PRACTICES.md)
21. [Style Summary](./STYLE_SUMMARY.md)
