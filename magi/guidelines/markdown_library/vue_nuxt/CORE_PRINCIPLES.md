# Core Principles

### Composition Over Options

All new components use the Composition API with `<script setup>`. The Options API is maintenance-mode only for legacy code that has not been migrated. Composition API provides superior TypeScript inference, composable extraction, and explicit dependency tracking. **Mixing Options and Composition API in the same component is prohibited.**

### Type Everything

Every prop, emit, ref, reactive object, composable return, API response, and Pinia state declaration carries explicit TypeScript types. Runtime prop validation supplements compile-time types for values crossing trust boundaries. The `any` type is prohibited. The `unknown` type is used for genuinely unknown values and narrowed immediately via type guards.

### Server-First Rendering

Nuxt 3 defaults to universal (SSR) rendering. Every page and layout must produce valid, complete HTML on the server. Client-side-only logic is the exception, not the rule. Components that depend on browser APIs (`window`, `document`, `localStorage`, `IntersectionObserver`) wrap in `<ClientOnly>` or guard with `import.meta.client` checks. **SSR-incompatible code that silently breaks hydration is worse than a visible error.**

### Zero-Waterfall Data Fetching

Data required for initial render fetches on the server, in parallel where possible, before the component tree mounts. Sequential client-side fetches that block visible content are performance defects. `useAsyncData` and `useFetch` execute server-side by default, transfer state to the client via payload, and avoid re-fetching on hydration. Every page-level data dependency uses these composables — never raw `fetch` or `axios` in component setup.

### Explicit State Ownership

Every piece of reactive state has a single, identifiable owner.

| Scope | Owner |
|:------|:------|
| Component-local | `ref` and `reactive` within the component |
| Cross-component | Pinia stores |
| Server-fetched | `useAsyncData` / `useFetch` caches keyed by unique identifiers |
| Service injection | `provide` / `inject` (services and configuration only — never application data) |

Duplicated state across multiple owners is a synchronization bug waiting to happen.

### Golden Rule

If Nuxt provides a composable, auto-import, or convention for it, **use the Nuxt way**. Custom abstractions that replicate built-in Nuxt functionality create maintenance burden without adding value. This includes routing (file-based), data fetching (`useAsyncData`/`useFetch`), state (`useState`/Pinia), middleware (file-based), server routes (Nitro), and config (`nuxt.config.ts` / runtime config).

---
[Back to Overview](./OVERVIEW.md)
