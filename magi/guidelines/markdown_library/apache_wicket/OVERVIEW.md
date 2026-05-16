# Apache Wicket Guidelines Library

This directory contains an expanded, modularized version of the Apache Wicket Guidelines. Mandatory for all server-side rendered Java web applications using Apache Wicket. Targets Wicket 9.x/10.x on Java 11+ (9.x) or Java 17+ (10.x), Jakarta Servlet 5+. Covers component architecture, the model system, HTML/Java separation, serialization discipline, session management, security, AJAX, and clustered deployments. Deviation is a correctness defect.

## Critical Mandates (Read First)
- **Components Own Their Markup** — Every Wicket component binds to exactly one HTML element via `wicket:id`.
- **Models Are Not Optional** — Every component that displays or edits data uses an `IModel`, never raw object references.
- **Strict HTML/Java Separation** — HTML templates contain zero logic. Templates define structure; Java defines behavior.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md) — Component-oriented architecture, server-side state, HTML/Java separation, model-driven design, type safety.
2. [Project Structure](./PROJECT_STRUCTURE.md) — Standard directory layout, HTML co-location, application class configuration.
3. [Component Architecture](./COMPONENT_ARCHITECTURE.md) — Component hierarchy, lifecycle, standard pattern, markup inheritance.
4. [Model System](./MODEL_SYSTEM.md) — Model types, `LoadableDetachableModel` pattern, common mistakes.
5. [HTML Markup](./HTML_MARKUP.md) — Wicket namespace, tags, template best practices.
6. [Forms and Validation](./FORMS_VALIDATION.md) — Form structure, components, validators.
7. [AJAX and Behaviors](./AJAX_BEHAVIORS.md) — Ajax components, behaviors, `AjaxRequestTarget`.
8. [Session and State](./SESSION_STATE.md) — `WebSession`, page parameters, stateless pages.
9. [Serialization](./SERIALIZATION.md) — Fundamentals, detachable models, transient fields, pitfalls.
10. [Security](./SECURITY.md) — Authentication, authorization, CSRF, CSP, output encoding.
11. [Resources and Header Contributions](./RESOURCES_HEADER.md) — Package resources, header contributions, resource bundles.
12. [Internationalization](./INTERNATIONALIZATION.md) — Resource bundles, `StringResourceModel`, locale selection.
13. [Dependency Injection](./DEPENDENCY_INJECTION.md) — Spring, CDI, no direct instantiation.
14. [Performance](./PERFORMANCE.md) — Session size, component tree, repeater optimization.
15. [Testing](./TESTING.md) — `WicketTester`, form testing, AJAX testing, mocking.
16. [Shakedown](./SHAKEDOWN.md) — Definition, triggers, validation categories, execution sequence, harness, classification, artifacts, anti-patterns.
17. [Deployment](./DEPLOYMENT.md) — `web.xml`, dev vs production mode, clustering.
18. [Defense in Depth](./DEFENSE_IN_DEPTH.md) — Independent layers, Rule of Three.
19. [Prohibited Practices](./PROHIBITED_PRACTICES.md) — Never Do / Always Do lists.
20. [Style Summary](./STYLE_SUMMARY.md) — Quick-reference table for required styles.
