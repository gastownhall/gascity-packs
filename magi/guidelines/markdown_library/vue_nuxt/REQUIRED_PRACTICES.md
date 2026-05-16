# Required Practices

### Always Do

- Use `<script setup lang="ts">` in every new component.
- Type all props, emits, refs, composable returns, API responses, and store state explicitly.
- Use `useAsyncData` or `useFetch` for all data needed during render. **Never raw `$fetch` in setup.**
- Provide unique, descriptive, namespaced keys for all `useAsyncData` calls.
- Guard all browser API access with `import.meta.client`, `onMounted`, or `<ClientOnly>`.
- Validate all server route input (body, query, params) with a runtime schema validator.
- Place all secrets in `runtimeConfig` (private). Use environment variables for production.
- Use the setup function syntax for all new Pinia stores.
- Route all store state mutations through actions.
- Handle and display error states from `useAsyncData`/`useFetch` in every page and component that fetches data.
- Use lazy components (`LazyXxx` prefix) for all below-the-fold and conditionally-rendered content.
- Use `<NuxtLink>` for all internal navigation links.
- Use `useSeoMeta` or `useHead` for all page-level meta tags. Provide title, description, and OG tags for every public page.
- Run E2E tests against a production SSR build in CI. Verify hydration, server routes, and middleware.
- Share validation schemas between client forms and server routes when validating the same data shape.
- Run shakedown against `nuxt build` + `nuxt preview` (or deployed preset output) on every triggering change.
- Capture all required shakedown artifacts (SSR HTML, payload, Playwright trace, Pinia snapshot, summary, issue list, env snapshot).

---
[Back to Overview](./OVERVIEW.md)
