# State Management

State management in React spans component-local state (`useState`, `useReducer`), shared state (context, Zustand, Jotai), and server state (TanStack Query, SWR). Each category has distinct tools and patterns. **Using the wrong tool for the category is the root cause of most state management complexity.**

### Client State vs Server State

| Category | Tool |
|:---------|:-----|
| Client state (UI toggles, form drafts, modal visibility, selected tabs) | `useState`, `useReducer`, Zustand, Jotai |
| Server state (API data, user profiles, product lists) | **TanStack Query (React Query)** or SWR |

Storing server data in Redux/Zustand/Context and manually managing loading, error, caching, refetching, and invalidation reimplements what TanStack Query does out of the box — worse.

### `useState` vs `useReducer`

| Use | When |
|:----|:-----|
| `useState` | Simple, component-local state |
| `useReducer` | Complex state with multiple sub-values, or when next state depends on previous state |

Type the reducer's state and action with discriminated unions:

```typescript
type Action =
  | { type: 'increment' }
  | { type: 'set'; value: number };

function reducer(state: number, action: Action): number {
  switch (action.type) {
    case 'increment': return state + 1;
    case 'set': return action.value;
  }
}
```

### React Context

Use Context for **low-frequency** shared state: theme, locale, auth status, feature flags. Do **not** use Context for high-frequency updates (form state, animation values, frequently changing lists). Context updates re-render every consumer — there is no selector mechanism. For high-frequency shared state, use **Zustand (with selectors)**, **Jotai (atomic model)**, or `useExternalSyncStore`.

When using Context, create a typed provider component and a typed consumer hook. Export the hook, not the raw context. The hook calls `useContext` internally and throws an informative error if used outside the provider:

```typescript
function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
```

This prevents silent `undefined` access when a component forgets to wrap in the provider.

### TanStack Query Key Factories

Define typed query functions and use queryKey factories for type-safe, consistent cache key management:

```typescript
const userKeys = {
  all: ['users'] as const,
  detail: (id: string) => ['users', id] as const,
};
```

This prevents key typos and enables targeted cache invalidation. The query function's return type flows through `useQuery`'s `data` type automatically.

---
[Back to Overview](./OVERVIEW.md)
