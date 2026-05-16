# State Management

State management strategy follows a hierarchy of **locality**:

1. Component state (`useState`, `useReducer`).
2. Shared component state (context, lifted state).
3. Server state (TanStack Query, SWR, framework data loaders).
4. Global client state (Zustand, Jotai, Redux Toolkit).

**Use the simplest mechanism that satisfies the requirement.**

### Server State vs Client State

| Category | Tool |
|:---------|:-----|
| Server state (data owned by the server, cached on the client) | TanStack Query, SWR — handles caching, invalidation, background refetching, stale management |
| Client state (UI state, form drafts, user preferences) | React state primitives or a lightweight state library |

**Mixing both in a single global store** (Redux holding API cache + UI state) creates unnecessary complexity.

### Choosing a Client State Library

| Library | When |
|:--------|:-----|
| Zustand | Simple stores |
| Jotai | Atomic state |
| React context | Small, infrequently-changing values |
| Redux Toolkit | Complex state with many reducers, middleware needs, time-travel debugging |

**Do not adopt Redux for state that fits in a single `useState` or `useReducer`.**

### Context Is DI, Not Global State

Context is a **dependency injection mechanism**, not a global state manager. Context triggers re-renders on every consumer when the value changes. **For frequently-changing state** (input values, animation frames, scroll position), context causes performance problems.

Split contexts by update frequency:

- ✓ `AuthContext` (changes rarely), `ThemeContext` (changes rarely).
- ✗ `FormStateContext` (changes on every keystroke) — performance problem.

### `useReducer` for Complex Transitions

Use `useReducer` for complex state transitions with multiple sub-values or when the next state depends on the previous state. **Type the reducer's action as a discriminated union** for exhaustive action handling:

```typescript
type Action =
  | { type: 'increment' }
  | { type: 'decrement' }
  | { type: 'reset'; payload: number };

function reducer(state: number, action: Action): number {
  switch (action.type) {
    case 'increment': return state + 1;
    case 'decrement': return state - 1;
    case 'reset': return action.payload;
  }
}
```

---
[Back to Overview](./OVERVIEW.md)
