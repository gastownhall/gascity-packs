# React 19 Component Architecture

React 19 introduces the **React Compiler** (automatic memoization), **Actions** for form handling, **Server Components** (stable), `useActionState`, `useFormStatus`, `useOptimistic`, and the `use()` hook.

### Function Components Only

All React components are function components with TypeScript. **Class components are prohibited in new code.** Function components with hooks provide the same capabilities with less boilerplate, better TypeScript inference, and compatibility with the React Compiler, Server Components, and concurrent features.

### Typed Props

Type component props with an `interface` or `type` alias, **never with inline object types** in the function signature. Export the props type alongside the component for consumer use:

```typescript
interface UserCardProps {
  /** The user record to display */
  user: User;
  /** Called when the card is selected */
  onSelect: (userId: string) => void;
}

export const UserCard = ({ user, onSelect }: UserCardProps): React.ReactElement => {
  // ...
};
```

Provide JSDoc descriptions on non-obvious props. **Use `React.FC` sparingly** — prefer direct function typing for explicit return type control.

### Manual Memoization Becomes Optional

With React 19's Compiler handling memoization automatically, **remove manual `useMemo` and `useCallback` wrappers unless profiling demonstrates they are still necessary**. The Compiler analyzes component dependencies and inserts memoization where beneficial. Manual memoization that the Compiler also optimizes adds complexity without benefit. **Measure with React Profiler to verify.**

### Single Responsibility

Components have a single responsibility. A component exceeding **200 lines of JSX + logic** is a candidate for decomposition:

- Extract data fetching into custom hooks.
- Extract complex UI sections into child components.
- Extract business logic into utility functions.

The component orchestrates rendering — it should not contain business logic, API calls, and complex state management simultaneously.

### React 19 Form Actions

Use the `<form action={serverAction}>` pattern instead of manual `onSubmit` handlers with `preventDefault`:

```typescript
'use server';
async function updateUser(formData: FormData) {
  // ...
}

// Component
<form action={updateUser}>
  <input name="email" />
  <SubmitButton />
</form>
```

Actions integrate with `useActionState` for pending/error state, `useFormStatus` for submission status, and `useOptimistic` for instant UI feedback. **This eliminates boilerplate** for manual loading state, error state, and form reset management.

### `use()` Hook

Use the `use()` hook for reading promises and context in render. `use()` can be called conditionally (unlike other hooks) and suspends the component until the promise resolves, integrating with Suspense boundaries for loading states. For data fetching in frameworks (Next.js, Remix), prefer the framework's data loading primitives; use `use()` for promise consumption within component trees.

### Server Components (React 19)

In frameworks supporting Server Components (Next.js 14+), **default to Server Components**. Add `'use client'` only when the component needs interactivity (hooks, event handlers, browser APIs).

| Constraint | Behavior |
|:-----------|:---------|
| Bundle size | Server Components reduce client bundle size |
| Data access | Direct database access in component body |
| Waterfalls | Eliminates client-server waterfalls for data fetching |
| Async | Server Components are async; Client Components cannot be async |
| Import direction | Never import a Server Component **from** a Client Component — Server → Client only |

Wrap async Server Components in **Suspense** boundaries for streaming and fallback UIs.

---
[Back to Overview](./OVERVIEW.md)
