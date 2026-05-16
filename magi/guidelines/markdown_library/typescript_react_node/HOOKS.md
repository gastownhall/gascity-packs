# Hooks Patterns

### Rules of Hooks

Call hooks at the top level of function components or custom hooks only — **never inside loops, conditions, or nested functions**. This is not a guideline; it is a structural requirement of React's hook state tracking. The ESLint plugin `react-hooks/rules-of-hooks` enforces this at lint time.

### Typing `useState`

```typescript
// Explicit type when initial value doesn't represent the full type range
const [user, setUser] = useState<User | null>(null);

// Inferred when initial value is sufficient
const [count, setCount] = useState(0);  // number

// Avoid useState<any> — always provide the specific type
```

### `useEffect` Discipline

Use `useEffect` **only for synchronization with external systems**:

- DOM manipulation
- Subscriptions
- Timers
- Network requests in non-framework contexts
- Browser API interactions

`useEffect` is **NOT** for:

- Derived state computation (use `useMemo` or compute inline).
- Event responses (use event handlers).
- Data fetching in frameworks that provide data loading primitives (Next.js, Remix, TanStack Query).

**Most new React 19 code needs fewer `useEffect` hooks than React 18 code.**

### Cleanup Functions

Return a cleanup function from `useEffect` when the effect creates subscriptions, timers, event listeners, or any resource that persists beyond the render cycle. Missing cleanup causes memory leaks, stale subscriptions, and race conditions:

```typescript
useEffect(() => {
  const id = setInterval(tick, 1000);
  return () => clearInterval(id);
}, []);
```

### `useEffectEvent` (React 19.2+)

Use `useEffectEvent` for stable event handlers referenced inside effects. `useEffectEvent` creates a function that always reads the latest props/state without triggering effect re-runs when those values change. **This eliminates the common pattern of adding values to the dependency array solely because they are referenced in a callback**, not because they should trigger re-execution.

### Custom Hooks

- Extract reusable stateful logic into custom hooks named with the `use` prefix: `useAuth`, `useDebounce`, `useLocalStorage`, `useMediaQuery`, `useIntersectionObserver`.
- One hook per file.
- Export the hook and its return type.
- **Return typed objects, not tuples,** when the return value has more than 2–3 elements:

```typescript
// Preferred for >2 fields
return { data, error, isLoading, refetch };

// Tuples acceptable for hooks mimicking useState
return [value, setValue];
```

---
[Back to Overview](./OVERVIEW.md)
