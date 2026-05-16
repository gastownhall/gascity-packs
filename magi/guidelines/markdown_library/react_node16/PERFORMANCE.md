# Performance

React performance optimization reduces unnecessary re-renders, minimizes JavaScript bundle size, and ensures responsive user interactions. **Optimization is measurement-driven, not intuition-driven.**

### Measure Before Optimizing

| Tool | Purpose |
|:-----|:--------|
| React DevTools Profiler | Identify components that re-render unnecessarily |
| React Scan | Highlight slow components |
| Lighthouse / Core Web Vitals (LCP, INP, CLS) | Page-level performance |

Do not add `useMemo`, `useCallback`, or `React.memo` without profiling evidence that the optimization addresses a measured problem.

### `React.memo`

Use `React.memo` for components that re-render with the same props due to parent re-renders. `React.memo` performs a shallow comparison of props and skips re-rendering when props are unchanged. Most effective for components that:

- Render expensive UI (lists, charts, tables)
- Receive stable props
- Sit below frequently-updating parents

**Do not memo every component** — the overhead of comparison can exceed the cost of re-rendering for simple components.

### `useCallback` and `useMemo`

Use `useCallback` for functions passed as props to memoized children. Without `useCallback`, a new function reference is created on every render, defeating `React.memo`'s shallow comparison. Use `useMemo` for expensive computations whose inputs change less frequently than the component renders. Both hooks require a correct dependency array — an incorrect array causes stale values or unnecessary recomputation.

### `useTransition`

Use `useTransition` for non-urgent state updates that cause expensive re-renders: filtering large lists, switching tabs with heavy content, updating search results. `useTransition` marks the update as non-urgent, allowing React to keep the UI responsive to user input while the expensive render completes in the background. Display a pending indicator (`isPending` from `useTransition`) to communicate that the update is processing.

### Virtualization

Virtualize long lists (**100+ items**). Use `@tanstack/react-virtual`, `react-window`, or `react-virtuoso` for windowed rendering that only creates DOM nodes for visible items. A 10,000-item list rendered fully creates 10,000 DOM nodes. A virtualized list creates 20–50 DOM nodes regardless of total list size. This eliminates the primary performance bottleneck for data-heavy UIs.

### Bundle Analysis

Analyze bundle size with a bundle analyzer (`vite-bundle-visualizer`, `@next/bundle-analyzer`, `webpack-bundle-analyzer`):

- Identify large dependencies.
- Use dynamic `import()` for libraries needed only on specific routes or interactions.
- Replace heavy libraries with lighter alternatives where possible (`date-fns` tree-shakes better than the deprecated `moment.js`).
- Target **under 200KB initial JavaScript (gzipped)** for content-focused pages.

---
[Back to Overview](./OVERVIEW.md)
