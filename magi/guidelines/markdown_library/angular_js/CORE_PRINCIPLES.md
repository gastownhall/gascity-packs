# Core Principles

These guidelines define strict, maintainable, and migration-ready patterns for AngularJS 1.x codebases, optimizing for:

- **Controlled Legacy Management**: AngularJS reached end-of-life in January 2022; every architectural decision prioritizes stability of existing systems and incremental migration toward modern Angular—not feature expansion on a dead framework.
- **Digest Cycle Awareness**: The dirty-checking change detection model is the source of every performance cliff in AngularJS.
- **Component-Oriented Architecture**: The component pattern introduced in 1.5 is the mandatory organizational unit for all view logic.
- **Unidirectional Data Flow**: Data flows down through bindings; events flow up through callbacks.
- **Dependency Injection Discipline**: Every injectable construct declares dependencies explicitly through annotation-safe patterns.

### Primary Rule: This Is Maintenance Mode

AngularJS is not a platform for new feature development. Every line of AngularJS written today must serve one of three purposes:
1. Fixing a defect.
2. Closing a security vulnerability.
3. Restructuring code to reduce migration cost.

New features belong in modern Angular, React, or another actively maintained framework. If the business requires new capabilities, build a migration bridge.

### Secondary Rule: Prepare Every File for Migration

Every controller, service, directive, and filter should be structured so that its logic is extractable into a modern Angular component, service, or pipe with minimal rewriting. Code that fights migration patterns today becomes code that blocks migration deadlines tomorrow.

### Version Strategy

These guidelines target AngularJS 1.5+ through 1.8.x (the final release), with **1.8.3 the recommended version**. Applications on versions earlier than 1.5 must prioritize upgrading to 1.8.x immediately.

### Dependency on jQuery

AngularJS includes jqLite. Full jQuery should not be loaded unless a third-party directive explicitly requires it. If jQuery is required, pin it to a specific version and isolate jQuery-dependent code to dedicated directives. Scattered jQuery usage is a maintenance nightmare and a migration blocker.

---
[Back to Overview](./OVERVIEW.md)
