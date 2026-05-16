# Performance Optimization

### OnPush as Foundation

OnPush change detection is the highest-impact performance decision. It eliminates unnecessary template checks across component subtrees. Mandatory for all components.

### Zoneless Angular

Target modern zone-free operation by:
- Using Signals for all state driving templates.
- Avoiding implicit zone.js triggers (`setTimeout` outside Angular context).
- Enabling `provideExperimentalZonelessChangeDetection()` in development.
- Replacing zone-dependent patterns with signal updates.

### Lazy Loading Strategy

- Every feature route uses `loadChildren` or `loadComponent`.
- Heavy components use `@defer` blocks with triggers (`on viewport`, `on idle`).
- Dynamically import third-party libraries within features.

### Bundle Optimization

- Configure `manualChunks` in build options.
- Use `withPreloading(PreloadAllModules)` for idle-time chunk loading.
- Enforce bundle budgets in `angular.json`.

### Runtime Performance

- **Track by identity**: Always provide `track` in `@for` blocks.
- **Minimize template expressions**: Move complex logic to `computed()` signals.
- **Virtual scrolling**: Use CDK `cdk-virtual-scroll-viewport` for lists > 100 items.
- **Image optimization**: Use `NgOptimizedImage` for lazy loading, priority hints, and preconnects.

```html
<img ngSrc="path/to/image.jpg" width="200" height="100" priority />
```

---
[Back to Overview](./OVERVIEW.md)
