# Routing and Navigation

### File-Based Routing

Nuxt generates routes from the `pages/` directory structure. **This is the only routing mechanism. Do not define routes manually in configuration.**

| Pattern | File |
|:--------|:-----|
| Dynamic | `pages/users/[id].vue` |
| Catch-all | `pages/[...slug].vue` |
| Optional parameter | `pages/[[id]].vue` |
| Nested | Directory nesting with a parent layout file |

The file system is the routing contract — changing a file name changes a route.

### Route Middleware

Route middleware runs before navigation resolves.

| Type | Definition |
|:-----|:-----------|
| Inline | `definePageMeta({ middleware: handler })` |
| Named | `middleware/auth.ts` |
| Global | `middleware/auth.global.ts` |

Named middleware registers automatically by file name. Middleware receives `to` and `from` route objects and can return `navigateTo()` for redirects or `abortNavigation()` for cancellation. Use middleware for auth guards, feature flags, and prerequisite checks. Middleware runs on both server (initial request) and client (subsequent navigation).

**Middleware must be fast.** Avoid async operations that add latency to every navigation. Auth checks should verify tokens from cookies or Pinia state, not make network requests. Prefetch auth state in a plugin or app-level middleware that runs once on initial load.

### Page Meta

`definePageMeta` sets per-page configuration: layout, middleware, page transitions, keepalive, and custom validation. The `validate` function receives the route and returns `true`/`false` or a redirect — use it for parameter validation (is the ID numeric? does this slug exist?) before the page component loads. **Page meta is extracted at build time and must use literal values, not runtime expressions.**

### Navigation Patterns

| Use case | API |
|:---------|:----|
| Internal links | `<NuxtLink>` — automatic prefetching, active class management, SPA navigation without full page reloads |
| Programmatic in script | `navigateTo()` |
| Advanced router operations | `useRouter()` |

**Never use `window.location` for internal navigation in a Nuxt app** — it triggers a full page reload, destroys SPA state, and bypasses middleware.

---
[Back to Overview](./OVERVIEW.md)
