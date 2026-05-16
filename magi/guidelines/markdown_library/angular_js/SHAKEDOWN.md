# Shakedown

### Definition

A shakedown is the first controlled end-to-end execution of the production AngularJS bundle against a real backend. It validates that bootstrap, the injector graph, ui-router resolution, and interceptors all operate correctly as an integrated whole.

### Mandatory Triggers

- AngularJS minor-version bumps.
- Modifying `.config()` or `.run()` blocks.
- Changing `$http` interceptors or ui-router resolve blocks.
- Upgrading jQuery plugins consumed by directives.
- Hybrid ngUpgrade steps.
- Deploying after long inactivity (>3 months).

### Validation Categories

1. **Bootstrap integrity**: App attaches without modulerr or dependency exceptions.
2. **Injector integrity**: All services/components resolve (survival of minification).
3. **Routing integrity**: State resolution and rendering in `ui-view`.
4. **HTTP integrity**: Interceptor execution and Authorization header injection.
5. **Digest integrity**: $scope digest settles without loop errors.
6. **Binding integrity**: User input round-trips correctly via `ng-model`.
7. **Cleanup integrity**: `$destroy` handlers fire and release resources.

### Execution Sequence

1. Preflight: Verification of minified bundle and annotations.
2. Serve production output on a loopback port.
3. Launch real browser (Playwright/Selenium) with console capture.
4. Navigate landing → authenticated → form submission.
5. Record network and console logs; classify results.

### Result Classification

- **Pass**: All categories hold.
- **Fail (blocking)**: Injector errors, resolve failures, or digest loops. Fix and re-run.
- **Fail (non-blocking)**: Deprecation warnings or non-breaking console noise.

**Forbidden: Running shakedown against unminified code or `$httpBackend` mocks.**

---
[Back to Overview](./OVERVIEW.md)
