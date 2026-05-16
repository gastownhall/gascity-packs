# Hooks

Hooks are the mechanism for state, side effects, context, and reusable logic in function components. TypeScript integration requires explicit typing for state, refs, context, and custom hook return values.

### `useState`

Type `useState` with the generic parameter when the initial value does not fully represent the type:

```typescript
const [user, setUser] = useState<User | null>(null);
const [tags, setTags] = useState<string[]>([]);
```

Let TypeScript infer when the initial value is sufficient: `useState(0)` infers `number`, `useState('')` infers `string`. **Explicitly typing inferred primitives is redundant noise.**

### `useRef`

Type `useRef` with the element type for DOM refs:

```typescript
const inputRef = useRef<HTMLInputElement>(null);
```

The initial value `null` indicates the ref is unassigned until mount. **Always check for `null`** before accessing `ref.current` in event handlers and effects — the ref is `null` during SSR and before the element mounts. For mutable value refs (timer ID, previous value), use `useRef<number | undefined>(undefined)`.

### `useEffect` Dependencies

`useEffect` dependencies **must be exhaustive**. The ESLint rule `react-hooks/exhaustive-deps` enforces this. **Do not disable the rule with eslint-disable comments.** If the effect runs too frequently with correct dependencies, the fix is restructuring the effect (extracting stable callbacks, using `useCallback`, moving logic outside the effect), not lying to the dependency array. An incorrect dependency array causes stale closures — one of the most common and difficult-to-debug React bugs.

### Effect Cleanup

Return cleanup functions from `useEffect` for every subscription, timer, event listener, and WebSocket connection. Cleanup runs on unmount and before each effect re-execution. Missing cleanup causes:

- Memory leaks
- Duplicate subscriptions
- State updates on unmounted components ("Can't perform a React state update on an unmounted component" warning in React 17; **silent bug in React 18+**)

```typescript
useEffect(() => {
  const id = setInterval(() => tick(), 1000);
  return () => clearInterval(id);
}, []);
```

### Rules of Hooks

Do not call hooks conditionally, inside loops, or after early returns. Hooks must execute in the same order on every render. The Rules of Hooks are enforced by `eslint-plugin-react-hooks` — install and enable this plugin. Violations cause corrupted hook state that manifests as seemingly random bugs across unrelated components.

### Custom Hooks

Extract reusable stateful logic into custom hooks prefixed with `use`: `useAuth`, `useDebounce`, `useLocalStorage`, `useMediaQuery`, `useIntersectionObserver`. Custom hooks are functions that call other hooks. They return typed values (state, handlers, computed values) as objects or tuples. **The return type is the hook's public API contract — type it explicitly.**

```typescript
function useDebounce<T>(value: T, options: { delay: number; maxWait?: number }): T {
  // implementation
}
```

Custom hooks that perform cleanup (subscriptions, timers, observers) must handle cleanup in their internal `useEffect`. The hook consumer should not need to know about cleanup — the hook encapsulates its own lifecycle. Test custom hooks independently with `@testing-library/react`'s `renderHook`.

For hooks accepting configuration, use an **options object with a typed interface** rather than positional parameters:

```typescript
useDebounce(value, { delay: 300, maxWait: 1000 }); // clearer, extensible
```

---
[Back to Overview](./OVERVIEW.md)
