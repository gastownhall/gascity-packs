# Build Configuration and Deployment

### Angular Configuration

The recommended builder is `@angular-devkit/build-angular:application` (ESBuild-based).

**Development**: Source maps enabled, optimization disabled, live reload active.

**Production**: AOT, tree shaking, minification, and bundle compression. Enable `subresourceIntegrity`.

### Environment Configuration

Prefer runtime configuration (e.g., via `APP_INITIALIZER`) for containerized deployments to use a single build artifact across multiple environments.

### Bundle Budgets

Enforce limits in `angular.json` to prevent size regressions:

```json
{
    "budgets": [
        { "type": "initial", "maximumWarning": "500kB", "maximumError": "1MB" }
    ]
}
```

### Deployment Artifacts

Build produces static files in `dist/`. Hosting platform must serve `index.html` for all routes (SPA fallback). SSR deployments produce a Node.js server entry point.

### CI Pipeline Structure

1. Install dependencies.
2. Lint: `ng lint` (zero warnings tolerance).
3. Type check: `tsc --noEmit`.
4. Unit/Component tests with coverage check.
5. Build: Production configuration + budget enforcement.
6. Shakedown against built artifact.
7. E2E tests.
8. Container build and Deploy.

Every step is mandatory. The pipeline is the gatekeeper.

---
[Back to Overview](./OVERVIEW.md)
