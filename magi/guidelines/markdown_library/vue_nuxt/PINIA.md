# Pinia State Management

### Setup Stores (Composition API Syntax)

Define Pinia stores using the **setup function syntax exclusively**. Setup stores use `defineStore` with a function that returns refs (state), computed values (getters), and functions (actions). This syntax mirrors composables, provides full TypeScript inference without type annotations on the store definition, and supports all Composition API features. The Options API store syntax is maintenance-mode only.

### Store Organization

One store per domain concept. `stores/auth.ts` manages authentication state. `stores/cart.ts` manages shopping cart state. `stores/ui.ts` manages UI state. **Stores are flat — do not nest stores or create store hierarchies.** When one store needs data from another, import and call the other store within an action. Avoid circular store dependencies by extracting shared logic into composables that both stores consume.

| Constraint | Required |
|:-----------|:---------|
| Naming | Store ID matches the file name: `defineStore('auth', ...)` in `stores/auth.ts`. Composable-style names (`useAuthStore`) are the convention for the exported function |
| Granularity | Avoid monolithic stores. A store managing user profile, authentication tokens, notification preferences, and session metadata splits into focused stores: `auth` (tokens, login state), `userProfile` (profile data), and `notifications` (preferences, queue) |

### Pinia in SSR Context

Pinia state initializes on the server and transfers to the client via Nuxt's payload. State set during server-side rendering (in middleware, plugin, or component setup) is available immediately on the client without re-fetching. Use this for auth state (populated from cookies in server middleware), user preferences, and initial data that all components need. Pinia stores are **per-request on the server** (each request gets a fresh store instance) but shared across the application lifecycle on the client.

**Do not mutate store state directly from components.** All state mutations flow through store actions. Actions encapsulate mutation logic, enable devtools tracking, and provide a single place to add validation, logging, or side effects when state changes.

### State Persistence

Use `pinia-plugin-persistedstate` (or equivalent) for state that must survive page reloads: cart contents, user preferences, draft form data. Configure persistence per-store, not globally. Specify the storage backend based on the data's sensitivity and required scope.

| Backend | Use |
|:--------|:----|
| Cookies | Required for state that must be available during SSR (auth tokens, locale) |
| `localStorage` | Client-only; unavailable during server rendering; fine for non-sensitive cross-session data |
| `sessionStorage` | Client-only; cleared on tab close; fine for transient cross-page state |

**Never persist sensitive tokens to `localStorage` in production** — use httpOnly cookies managed by server middleware.

### Store Testing

Test stores independently from components. Create a test Pinia instance with `createPinia()` and `setActivePinia()`. Test actions by calling them directly and asserting state changes. Mock API calls within actions using `vi.mock` or dependency injection. Test getters by setting state directly and asserting computed output. Test store interactions by instantiating both stores in the test and verifying cross-store behavior.

---
[Back to Overview](./OVERVIEW.md)
