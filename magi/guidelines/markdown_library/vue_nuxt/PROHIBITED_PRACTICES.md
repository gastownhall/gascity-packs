# Prohibited Practices

### Never Do

- Use the Options API in new components. Composition API with `<script setup>` is the standard.
- Use the `any` type. Use `unknown` and narrow with type guards.
- Use `$fetch` or raw `fetch()` in component setup for render data — causes double-fetching.
- Access `window`, `document`, `localStorage`, or `navigator` in `setup` outside `onMounted` or `import.meta.client` guards.
- Mutate Pinia store state directly from components. Use store actions for all mutations.
- Define routes manually instead of using file-based routing. The `pages/` directory is the routing contract.
- Use `window.location` for internal navigation. Use `navigateTo()` or `<NuxtLink>` for SPA navigation.
- Use the runtime props array syntax (`props: ['title']`) in new components. Use `defineProps` with TypeScript generics.
- Ignore or suppress hydration mismatch warnings. **Every mismatch is a bug with a deterministic cause.**
- Place secrets in `runtimeConfig.public`. Public config serializes into the client bundle.
- Process request bodies or query parameters in server routes without schema validation.
- Fetch entire collections without pagination in `useAsyncData`/`useFetch`. Payload size directly impacts page weight.
- Use `provide`/`inject` for application data flow. Use Pinia stores or composables for shared state.
- Ignore the `error` return from `useAsyncData`/`useFetch`. Display error states in templates.
- Call composables with lifecycle hooks after an `await` in setup. Breaks component instance association.
- Skip shakedown after a routeRules, middleware, Nitro preset, or Pinia persistence change.
- Run shakedown against `nuxt dev` or with a mocked backend.

---
[Back to Overview](./OVERVIEW.md)
