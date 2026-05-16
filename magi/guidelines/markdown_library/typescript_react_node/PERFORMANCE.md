# Performance

**Measure before optimizing.** Tools: Lighthouse, React Profiler, Chrome DevTools Performance tab, Node.js `--inspect` with Chrome DevTools, `clinic.js`.

### Code Splitting

Code-split at the route level using `React.lazy()` and dynamic `import()`. Each route loads only the JavaScript it needs. For large components within a route (modals, charts, editors), use `React.lazy` for component-level splitting. Suspense provides the loading fallback.

**Target under 200KB initial JavaScript (gzipped) for content pages.**

### Bundle Size Monitoring

Use `vite-bundle-visualizer` or `webpack-bundle-analyzer` to inspect chunk composition. Identify and eliminate large dependencies imported for small utilities. **Use tree-shakeable libraries and import only needed exports:**

```typescript
// Good
import { debounce } from 'lodash-es';

// Bad
import _ from 'lodash';  // imports everything
```

### Streaming in Node.js

Use streaming for large responses (file downloads, large JSON datasets, SSR HTML):

- Node.js streams (`Readable`, `Transform`, `pipeline()`) instead of buffering entire responses in memory.
- Streaming reduces memory consumption and time-to-first-byte.
- For SSR, use **React 19's `renderToPipeableStream`** for streaming HTML delivery.

### React 19 Concurrent Features

| Feature | Use |
|:--------|:----|
| `useTransition` | Non-urgent state updates (search, filtering, tab switching) |
| `useDeferredValue` | Deferring expensive re-renders |
| `Suspense` | Streaming data loading |

These features keep the UI responsive during heavy computation or slow data fetches **without manual optimization**.

---
[Back to Overview](./OVERVIEW.md)
