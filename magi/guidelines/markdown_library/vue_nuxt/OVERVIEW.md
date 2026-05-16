# Vue 3 and Nuxt 3 Development Library

**Runtime:** Vue 3.4+, Nuxt 3.10+, TypeScript 5.3+, Node 20 LTS+, Nitro 2.8+

Defines strict conventions for Vue 3 Composition API, Nuxt 3 rendering strategies, state management, data fetching, form validation, hydration safety, server routes, and full-stack TypeScript discipline. Applies to every frontend and full-stack application built on Vue 3 and Nuxt 3 — SSR, SSG, ISR, SPA modes; Pinia stores; Nitro server routes; API integrations.

## Critical Mandates (Read First)

- **Composition Over Options** — All new components use `<script setup>`; mixing Options and Composition API in the same component is prohibited.
- **Type Everything** — Every prop, emit, ref, reactive object, composable return, API response, and Pinia state declaration carries explicit TypeScript types; `any` is prohibited.
- **Server-First Rendering** — Every page and layout must produce valid, complete HTML on the server; SSR-incompatible code that silently breaks hydration is worse than a visible error.
- **Zero-Waterfall Data Fetching** — Use `useAsyncData`/`useFetch` for render data; never raw `$fetch` or `axios` in component setup.
- **Explicit State Ownership** — Every piece of reactive state has a single, identifiable owner; duplicated state is a synchronization bug waiting to happen.
- **Golden Rule** — If Nuxt provides a composable, auto-import, or convention for it, use the Nuxt way.
- **Shakedown Required** — `nuxt build` + `nuxt preview` against staging on every triggering change before deployment.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [TypeScript Discipline](./TYPESCRIPT.md)
3. [Vue 3 Composition API](./COMPOSITION_API.md)
4. [Nuxt 3 Rendering Strategies](./RENDERING.md)
5. [Hydration Safety](./HYDRATION.md)
6. [Data Fetching](./DATA_FETCHING.md)
7. [Pinia State Management](./PINIA.md)
8. [Nitro Server Routes](./NITRO.md)
9. [Form Handling and Validation](./FORMS.md)
10. [Routing and Navigation](./ROUTING.md)
11. [Layouts and Components](./LAYOUTS.md)
12. [Configuration and Runtime Config](./CONFIGURATION.md)
13. [SEO and Head Management](./SEO.md)
14. [Performance](./PERFORMANCE.md)
15. [Testing](./TESTING.md)
16. [Modules and Plugins](./MODULES_PLUGINS.md)
17. [Deployment](./DEPLOYMENT.md)
18. [Shakedown — Integration Validation](./SHAKEDOWN.md)
19. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
20. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
21. [Required Practices](./REQUIRED_PRACTICES.md)
22. [Style Summary](./STYLE_SUMMARY.md)
