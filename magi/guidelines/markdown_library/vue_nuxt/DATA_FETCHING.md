# Data Fetching

### useAsyncData

`useAsyncData` wraps any async function, executes it server-side, serializes the result into the Nuxt payload, and provides the cached result on the client without re-execution. Use for data fetching logic that does not map to a single HTTP request or that calls internal server functions.

| Constraint | Required |
|:-----------|:---------|
| Key uniqueness | Keys must be **globally unique** across all `useAsyncData` and `useFetch` calls. Use a pattern like `feature:identifier` (e.g., `'product:' + productId`) |
| `lazy: true` | For data not needed for the initial render (below-the-fold, secondary tabs); executes on the client after hydration |
| `transform` | Reshape API responses before caching; reduces payload size by stripping unnecessary fields server-side |
| `watch` | Re-execute when reactive dependencies change; explicit refs/computed only — do not watch entire reactive objects |
| Error handling | Check `error.value`. Display error states in the template. Use `<NuxtErrorBoundary>` or `definePageMeta` with `validate` for page-level errors. **Never ignore async data errors silently** |

### useFetch

`useFetch` is a convenience wrapper around `useAsyncData + $fetch`. It auto-generates a unique key from the URL and options, handles request/response typing, and supports all `useAsyncData` options. Use for straightforward HTTP requests to external APIs or Nuxt server routes. The auto-generated key incorporates URL and serializable options — changing query parameters automatically triggers a fresh fetch.

| Constraint | Required |
|:-----------|:---------|
| Server routes | When calling Nuxt server routes (`server/api/`), `useFetch` infers response types from the server route's return type — end-to-end type safety without duplicate type definitions |
| Base URL | Set via `runtimeConfig.public.apiBaseUrl` and reference in `useFetch` rather than hardcoding URLs |
| Interceptors | `onRequest`, `onRequestError`, `onResponse`, `onResponseError` for cross-cutting concerns; define shared interceptors in a `useApiFetch` composable |
| Deduplication | Nuxt deduplicates concurrent `useFetch` calls with the same key automatically — **do not implement manual deduplication** |

### $fetch (ofetch)

`$fetch` is the underlying HTTP client (`ofetch`) available globally in Nuxt. **Use `$fetch` directly only in event handlers, Pinia actions, server routes, and other non-setup contexts** where `useAsyncData`/`useFetch` composables cannot be called. Using `$fetch` in component setup causes double-fetching: once on the server, once on the client, because `$fetch` does not integrate with Nuxt's payload transfer. **This is the single most common data fetching mistake in Nuxt applications.**

**Never use `$fetch` or raw `fetch()` in component setup for data needed during render.** Use `useAsyncData` or `useFetch`.

### Data Refresh Patterns

`useAsyncData` and `useFetch` return a `refresh()` method that re-executes the handler and updates reactive state. Use `refresh()` after mutations (form submissions, state changes) to synchronize displayed data with server state. Use `refreshNuxtData()` to refresh specific keys or all cached data globally. For real-time data, combine `useFetch` with a polling interval via the `watch` option and a periodic ref update, or integrate WebSocket updates that call `refresh()` on relevant events.

---
[Back to Overview](./OVERVIEW.md)
