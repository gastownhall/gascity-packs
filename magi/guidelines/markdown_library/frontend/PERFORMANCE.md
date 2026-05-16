# Performance Optimization

### Memoization Decision Tree

Use `React.memo` when:
1. Component receives stable props.
2. Parent re-renders frequently.
3. Component has expensive render.

Use `useMemo` when:
1. Computation is expensive (O(n) or higher).
2. Result is used as a dependency.
3. Reference equality matters.

Use `useCallback` when:
1. Function is passed to a memoized component.
2. Function is a dependency of an effect.
3. Creating the function is expensive.

```tsx
import { memo, useMemo, useCallback } from 'react'

const ExpensiveChild = memo(({ data, onAction }) => {
  return <div>{/* ... */}</div>
})

function Component({ items, filter }) {
  const filtered = useMemo(
    () => items.filter(item => item.matches(filter)),
    [items, filter]
  )

  const handleClick = useCallback((id: string) => {
    // Handler logic
  }, [/* dependencies */])

  return <ExpensiveChild data={filtered} onAction={handleClick} />
}
```

Avoid premature memoization:

```tsx
// WRONG: useless memoization on cheap operations
const SimpleComponent = memo(({ text }) => {
  const upperText = useMemo(() => text.toUpperCase(), [text]) // Unnecessary
  const handleClick = useCallback(() => console.log('click'), []) // Unnecessary
  return <div onClick={handleClick}>{upperText}</div>
})
```

### Code Splitting

Route-based:

```tsx
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Settings = lazy(() =>
  import('./pages/Settings').then(module => ({ default: module.Settings }))
)
```

Component-based with chunk naming:

```tsx
const HeavyChart = lazy(() =>
  import(/* webpackChunkName: "charts" */ './components/HeavyChart')
)
```

Conditional loading:

```tsx
function ConditionalComponent({ shouldLoad }) {
  const [Component, setComponent] = useState(null)
  useEffect(() => {
    if (shouldLoad) {
      import('./HeavyComponent').then(mod => {
        setComponent(() => mod.default)
      })
    }
  }, [shouldLoad])

  return Component ? <Component /> : null
}
```

### Intersection Observer for Lazy Visibility

```tsx
function LazyImage({ src, alt }) {
  const ref = useRef<HTMLImageElement>(null)
  const [isInView, setIsInView] = useState(false)

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsInView(true)
          observer.disconnect()
        }
      },
      { threshold: 0.1 }
    )

    if (ref.current) {
      observer.observe(ref.current)
    }
    return () => observer.disconnect()
  }, [])

  return (
    <img ref={ref} src={isInView ? src : undefined} alt={alt} loading="lazy" />
  )
}
```

### Bundle Optimization

Constraints:
- Per-chunk size: **max 200KB**.
- Initial bundle: **max 100KB**.

```typescript
// Import specific functions, not entire library
import { debounce } from 'lodash-es/debounce'
// NOT: import _ from 'lodash'

// Use dynamic imports for large libraries
const loadChart = async () => {
  const { Chart } = await import('chart.js')
  return new Chart(/* ... */)
}
```

**Performance Rules:**

- Use `lazy()` for route-level components and heavy imports.
- Use `memo()` for components with expensive renders or stable props.
- Use `useMemo()` for expensive computations.
- Use `useCallback()` for functions passed to child components.
- Avoid creating objects or arrays in render unless necessary.
- Use `key` prop correctly in lists with stable unique identifiers; never use array index as key.
- Implement virtualization for large lists with `react-virtual`.
- Monitor bundle size and chunk sizes regularly.
- Use React DevTools Profiler to identify performance bottlenecks.

---
[Back to Overview](./OVERVIEW.md)
