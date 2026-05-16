# Shakedown — Production Bundle Validation

### Definition

A frontend shakedown is a **post-build mount smoke that loads the production React bundle in a real browser and verifies the integrated application boots, routes, fetches, and renders without console noise**. It runs against the production build, not the dev server.

A shakedown answers one question: *Does the emitted bundle boot against the real backend and render the canonical happy path with zero console errors?*

### Shakedown vs Unit vs E2E

| Layer | Scope |
|:------|:------|
| Unit tests (Vitest + jsdom) | Isolated components and hooks |
| Playwright E2E suite | User behaviour across many paths in production-like builds |
| **Shakedown** | **One known-good path against the emitted production bundle served statically** |

Forbidden:
- Treating shakedown as a Vitest/Jest replacement.
- Treating shakedown as the Playwright E2E suite.
- Running shakedown against the dev server (`vite dev` / `webpack-dev-server`) — HMR masks production failure modes.

### Mandatory Triggers

A shakedown is required after:

- First production build of a new application.
- Upgrading React, React Router, TanStack Query, SWR, or the bundler (Vite, webpack, rspack).
- Changing the root providers (`QueryClientProvider`, auth context, theme, router).
- Adding or removing a route in the top-level router configuration.
- Introducing or restructuring a dynamic import chunk boundary.
- Changing the global error boundary or error reporting hook.
- Rotating or restructuring environment variable names consumed via `import.meta.env`.
- Deploying to a new CDN, reverse proxy, or base path.

### Non-Triggers

A shakedown is not required for:

- Copy or text changes inside an existing validated component.
- CSS-only changes that do not alter layout of critical above-the-fold content.
- Pure unit test additions that do not touch production source.
- Documentation updates.

### Validation Categories

A shakedown must cover:

1. **Root mount** — `ReactDOM.createRoot(...).render(<App />)` produces the expected shell in the DOM.
2. **Router** — `createBrowserRouter` (or equivalent) resolves the landing route and one nested critical route.
3. **Server state** — `QueryClient` or SWR client initializes, issues exactly one fetch against the real API, and hydrates the cache.
4. **Auth context** — the auth provider hydrates from configured storage and exposes the expected user identity.
5. **Error boundary** — a canary error thrown inside a sacrificial child is caught and reported via the global boundary.
6. **Console cleanliness** — `console.error` and `console.warn` counts are zero for the happy path.
7. **Styling** — the critical CSS bundle applies; computed styles match the reference snapshot for above-the-fold elements.
8. **Code splitting** — dynamic `import()` chunks for the critical feature route load successfully.
9. **Feature flags** — the feature flag client resolves and exposes the expected default set for the fixture user.

### Execution Principles

- **Conservative** — a single fixture user with a documented expected dashboard.
- **Progressive** — landing route → nested critical route → one mutation → logout. Stop at the first failure.
- **Controlled** — staging API gateway with sandbox credentials, never production.
- **Observable** — full Playwright trace, console capture, network HAR, and screenshots per step.
- **Known-good** — inputs whose expected outputs are documented in the shakedown script.

Forbidden during shakedown:

- Optimizing bundle size, lazy chunking, or React Query cache.
- Mocking `fetch`, MSW, or any network layer.
- Running against `vite preview` when the production deploy uses a different static host configuration.

### Execution Sequence

| Step | Action |
|:----:|:-------|
| 1 | Preflight: production build passes with zero warnings; bundle budgets respected |
| 2 | Serve `dist/` via a static file server bound to a loopback port |
| 3 | Launch Playwright in headless Chromium with trace, console, and network capture enabled |
| 4 | Navigate to the landing route; assert the root element contains the expected shell markup |
| 5 | Assert the React Router outlet rendered the landing view |
| 6 | Navigate to a critical authenticated route; assert the dynamic import chunk loaded |
| 7 | Assert the TanStack Query / SWR client issued exactly one request to the real API gateway |
| 8 | Assert the auth context is populated with the fixture user identity |
| 9 | Trigger a canary error inside a sacrificial child; assert the global error boundary caught it |
| 10 | Inspect console counts: zero errors, zero warnings for the happy path |
| 11 | Record artifacts and classify the result |

### Result Classification

- **Pass** — every validation category holds; proceed to the broader E2E suite and deployment.
- **Fail — blocking** — root mount failure, router resolution failure, fetch never issued, auth hydration failure, or console error. Fix root cause and re-run from step 1.
- **Fail — non-blocking** — deprecation warning, slower-than-expected chunk load, or non-critical telemetry noise. Log the issue with reproduction context and proceed with caution.
- **Inconclusive** — staging API returned an unexpected payload unrelated to the change. Adjust the fixture and re-run the affected validation.

### Required Artifacts

- Playwright trace including console, network HAR, and screenshots per step.
- Result summary per validation category.
- Issue list with blocking / non-blocking / deferred classification.
- Environment snapshot: React version, router version, TanStack Query version, bundler version, bundle hash, staging API gateway URL, feature flag provider build id.

### Anti-Patterns (Forbidden)

- Skipping shakedown after a "small" provider reorder — provider order changes break hydration assumptions.
- Expanding shakedown into dozens of assertions across many routes.
- Running shakedown against `vite dev` with HMR.
- Mocking the API gateway, auth provider, or feature flag service during shakedown.
- Pausing shakedown to tune bundle size or chunk boundaries.
- Discarding the Playwright trace and HAR after the run.

---
[Back to Overview](./OVERVIEW.md)
