# Shakedown

### Definition

A shakedown is the first controlled end-to-end execution of the production bundle against the real API gateway in a headless browser. It validates that bootstrap, routing, HTTP, interceptors, and change detection operate correctly together.

### Mandatory Triggers

- First production build of a new app.
- Upgrading Angular or build tools.
- Switching to `bootstrapApplication` or altering core providers.
- Reordering `HttpInterceptorFn` entries.
- Enabling/reconfiguring hydration or zoneless operation.
- Deploying to a new CDN or reverse proxy.

### Validation Categories

1. **Bootstrap integrity**: Resolves providers and renders root component.
2. **Router integrity**: Default route resolves and lazy features load correctly.
3. **HTTP integrity**: Real round-trip against API gateway succeeds.
4. **Interceptor chain**: Auth/telemetry interceptors execute in order.
5. **Reactive lifecycle**: Subscriptions terminate on navigation (no leaks).
6. **Change detection**: Template updates correctly with new data.
7. **PWA integrity**: Service worker registers and fetches `ngsw.json`.
8. **Silent-error integrity**: Zero browser console errors/warnings.

### Execution Sequence

1. `ng build --configuration production`.
2. Serve `dist/` via static server.
3. Launch Playwright (headless).
4. Navigate to landing route.
5. Navigate to authenticated route (verify lazy chunk and interceptor).
6. Assert console cleanliness.
7. Capture heap snapshot (check for leaks).
8. Record artifacts and classify results.

### Result Classification

- **Pass**: All assertions held.
- **Fail (blocking)**: Bootstrap failure, chunk not loading, console errors. Fix and re-run.
- **Fail (non-blocking)**: Deprecation warnings or minor leaks. Log and proceed with caution.
- **Inconclusive**: Staging API returned unexpected payload shape.

### Required Artifacts

- Playwright trace (console, network, screenshots).
- Result summary per category.
- Issue list (blocking/non-blocking).
- Environment snapshot (Angular version, bundle hash, etc.).

**Forbidden: Mocking HttpClient or API gateway during shakedown.**

---
[Back to Overview](./OVERVIEW.md)
