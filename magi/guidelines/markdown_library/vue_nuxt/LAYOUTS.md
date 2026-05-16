# Layouts and Components

### Component Organization

Nuxt auto-imports components from `components/`. Organize by feature or domain: `components/auth/LoginForm.vue`, `components/product/ProductCard.vue`. Nuxt resolves component names from the directory path: `components/product/Card.vue` auto-registers as `<ProductCard>`. Use the `components.pathPrefix` option if the auto-generated names conflict. **Keep components focused on a single responsibility.** A component exceeding 200 lines of template + script is a candidate for decomposition.

### Layouts

Layouts wrap page content and provide shared structure (header, footer, sidebar). The default layout (`layouts/default.vue`) applies to all pages unless overridden via `definePageMeta({ layout: 'admin' })`. Layouts must include a `<slot>` element where page content renders. Layout transitions animate between layouts during navigation. **Keep layout logic minimal — layouts are structural containers, not business logic hosts.**

### Lazy and Async Components

Prefix component names with `Lazy` to enable automatic code splitting: `<LazyProductReviews>` loads the component only when it appears in the DOM. Use lazy components for below-the-fold content, modals, tabs, and any component not needed on initial render. This reduces the initial JavaScript bundle. `defineAsyncComponent` provides a lower-level API for custom loading/error states, but the `LazyXxx` prefix is preferred for Nuxt projects.

### Error Boundaries

`<NuxtErrorBoundary>` catches errors in its child component tree and renders a fallback UI via the `#error` slot. Use error boundaries around sections that fetch data independently or render third-party content. The error slot receives the error object for display. Call `clearError()` to recover and re-render the child tree. Page-level errors use `error.vue` at the project root for a full-page error experience.

---
[Back to Overview](./OVERVIEW.md)
