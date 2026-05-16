# Style Summary

| Element | Required pattern |
|:--------|:-----------------|
| **Vue 3** | Composition API with `<script setup>` exclusively; type all props/emits/refs; composables for reusable logic; no Options API in new code |
| **TypeScript** | strict mode; no `any`; type all boundaries; zod/valibot schemas for runtime validation with inferred types; narrow `unknown` immediately |
| **Rendering** | Universal SSR default; SSG for static content; ISR for CDN performance with freshness; SPA only for authenticated dashboards; per-route via `routeRules` |
| **Hydration** | Server HTML must match client render exactly; guard browser APIs; use `<ClientOnly>` with fallback slots; `useState` for cross-boundary consistency; fix mismatches, never suppress |
| **Data Fetching** | `useAsyncData`/`useFetch` for render data; unique namespaced keys; lazy for non-blocking; transform to reduce payload; `$fetch` only in event handlers and actions |
| **Pinia** | Setup store syntax; one store per domain; actions for all mutations; SSR-aware initialization; cookie persistence for SSR-required state |
| **Nitro** | File-based server routes; validate all input with schemas; `server/utils` for shared logic; server middleware for cross-cutting concerns; `createError` for HTTP errors |
| **Forms** | VeeValidate with zod/yup schemas; shared schemas between client and server; server error mapping to field errors; hydration-safe initial values |
| **Performance** | Under 200 KB initial JS gzipped; lazy components for below-fold; optimize payload size; Nuxt Image for media; monitor Core Web Vitals in production |
| **Routing** | File-based only; middleware for guards; `definePageMeta` for page config; `<NuxtLink>` for internal navigation; `navigateTo` for programmatic |
| **Configuration** | `runtimeConfig.public` for client-visible values; `runtimeConfig` for secrets; `.env` for dev; environment variables for production; fail fast on missing config |
| **Testing** | Vitest + `@vue/test-utils` for unit; Playwright/Cypress for E2E; test against SSR builds; mock `$fetch` and APIs; test stores independently |
| **Shakedown** | `nuxt build` + `nuxt preview` (never `nuxt dev`); 10 validation categories; SSR/SSG/ISR each have distinct paths; 7 required artifacts; pass/fail-blocking/fail-nonblocking/inconclusive |
| **Defense in Depth** | TypeScript + ESLint + Vitest + runtime validation + Playwright + Nuxt build/preview = six independent layers; type-check + component tests + browser E2E = the Rule of Three quorum |

---

**Apply these guidelines universally to all Vue 3 and Nuxt 3 development.**

---
[Back to Overview](./OVERVIEW.md)
