# React/TypeScript SPA Frontend Development Library

This directory contains an expanded, modularized version of the React/TypeScript SPA Frontend Development Guidelines. Apply universally to all React/TypeScript single-page applications.

## Critical Mandates (Read First)
- **Production-Ready or Nothing** — every line of code must meet production standards from the start.
- **Zero `any` types** — strict TypeScript with comprehensive compile-time validation.
- **Quality Gates** — zero errors, zero warnings, 90%+ test coverage, Lighthouse 90+ scores.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md) — Type safety, single source of truth, performance, maintainability, quality gates.
2. [Project Architecture](./PROJECT_ARCHITECTURE.md) — Directory structure, file naming.
3. [Technology Stack and Tooling](./TECH_STACK.md) — Dependencies, Vite, TypeScript configs.
4. [React 19+ Patterns](./REACT_PATTERNS.md) — `use()` hook, Server Components, React Compiler compatibility.
5. [TypeScript 5.x Strict Patterns](./TYPESCRIPT_STRICT.md) — `satisfies`, const type parameters, safe indexed access, type definitions.
6. [Component Design Patterns](./COMPONENT_DESIGN.md) — Component structure, composition over configuration.
7. [State Management with Zustand](./ZUSTAND_STATE.md) — Slices, middleware, computed values, selective persistence.
8. [Data Fetching with TanStack Query](./TANSTACK_QUERY.md) — Query hooks, mutations, infinite queries, providers, API layer.
9. [Form Handling and Validation](./FORMS_VALIDATION.md) — Zod + React Hook Form, field arrays, contact form.
10. [Routing and Navigation](./ROUTING.md) — React Router v6 with lazy loading.
11. [Styling and Theme System](./STYLING_THEME.md) — Centralized theme, Tailwind, conditional classes, cva variants.
12. [Performance Optimization](./PERFORMANCE.md) — Memoization, code splitting, lazy visibility, bundle optimization.
13. [Error Handling and Loading States](./ERROR_HANDLING.md) — Granular error boundaries, async, data components.
14. [Accessibility (WCAG 2.1 AA)](./ACCESSIBILITY.md) — Semantic HTML, ARIA, keyboard navigation, color contrast.
15. [Testing Strategy](./TESTING_STRATEGY.md) — Vitest, unit tests, component tests, MSW, E2E with Playwright, coverage.
16. [Build Pipeline and Quality Gates](./BUILD_QUALITY_GATES.md) — Build commands, quality gates, pre-commit hooks.
17. [Environment Configuration](./ENVIRONMENT_CONFIG.md) — Type-safe env vars validated at boot.
18. [Code Organization and Imports](./IMPORTS.md) — Import order and rules.
19. [Production Deployment](./PRODUCTION_DEPLOYMENT.md) — Docker multi-stage, Nginx config.
20. [Shakedown — Production Bundle Validation](./SHAKEDOWN.md) — Definition, triggers, validation categories, execution, classification.
21. [Defense in Depth](./DEFENSE_IN_DEPTH.md) — Independent layers, Rule of Three.
22. [Prohibited Practices](./PROHIBITED_PRACTICES.md) — Never Do list.
23. [Required Practices](./REQUIRED_PRACTICES.md) — Always Do list.
24. [Style Summary](./STYLE_SUMMARY.md) — Quick-reference table for required styles.
