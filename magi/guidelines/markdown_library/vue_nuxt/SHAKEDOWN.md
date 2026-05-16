# Shakedown — Integration Validation

### Definition

A Nuxt shakedown is a **dual-mode integration validation of a production build**: server-side rendering produces complete HTML on a representative request, the browser client hydrates the rendered markup into an interactive Vue application without mismatch warnings, and both rendering halves share the same data, state, middleware, and composable contracts. Shakedown answers a single question: **does this Nuxt application, built for production and served via the configured Nitro preset, execute correctly as an integrated whole across SSR and CSR?**

### Preflight vs Shakedown vs Testing

| Phase | What it validates |
|:------|:------------------|
| **Preflight** | Static gate: `nuxt build` succeeds, type checks pass, environment variables resolve, `nitro.preset` is set, required secrets exist in `runtimeConfig` |
| **Shakedown** | First controlled run of the built artifact against the real backend, exercising SSR and CSR along a single known-good path |
| **Testing** | Ongoing Vitest and Playwright work asserting behavior across many paths |

A Nuxt application that passes preflight is **ready to start**. A Nuxt application that passes shakedown is **known to render, hydrate, and fetch correctly**. A Nuxt application that passes testing is **known to behave correctly across its documented feature set**.

**Shakedown runs against `nuxt build` + `nuxt preview` (or the deployed Nitro preset output), never against `nuxt dev`.** Development mode has different bundling, HMR wiring, and SSR transform behavior, and cannot reproduce production integration faults.

### Mandatory Triggers

Shakedown is required and is **not optional** in these situations:

- First production build of a new Nuxt application.
- Nuxt, Nitro, Vue, or Vite major or minor version upgrade.
- Switching `nitro.preset` (`node-server`, `vercel`, `netlify`, `cloudflare-pages`, `static`).
- Adding, removing, or modifying `routeRules` that affect SSR/SSG/ISR mode for a critical route.
- Adding, removing, or reordering server middleware or route middleware on a critical path.
- Changing Pinia persistence backend for auth or session state.
- Adding a new `<ClientOnly>` boundary or removing an existing one.
- Initial setup or restructuring of `@nuxtjs/i18n` locale configuration.
- Renaming keys in `runtimeConfig` or `runtimeConfig.public`.
- Deploying to a new host, CDN, or edge environment.

### Non-Triggers

Handled by preflight and the regular test suite — do **not** require a shakedown run:

- Copy changes inside an existing page template with no new composable calls.
- Adding a new Vitest or `@nuxt/test-utils` test.
- Incrementing constant values inside validated route rules (TTL adjustment within the same mode).
- Style-only changes inside a component's scoped style block.

### Validation Categories

Every Nuxt shakedown run must cover these integration surfaces across both the SSR and CSR halves of the dual-mode lifecycle.

| Category | What is verified |
|:---------|:-----------------|
| Server build start | The Nitro-built server artifact starts on the configured port, initializes plugins, and accepts a request without unhandled exceptions during cold start |
| SSR render | A request to the critical landing route renders valid, complete HTML server-side with the fixture user's expected data embedded in `__NUXT_DATA__` |
| Hydration cleanliness | Client-side Vue hydration attaches to the server-rendered DOM with **zero "Hydration node mismatch" warnings** in the browser console |
| Async data contracts | `useAsyncData` and `useFetch` on the landing route execute server-side, serialize results into the payload, and **do not re-execute on hydration** |
| Pinia SSR restore | Pinia stores initialized in server middleware (auth, locale, user profile) restore correctly on the client via payload, with state identical between server render and client hydration |
| Middleware (both modes) | Route and server middleware fire **once** on the initial SSR request and **again** on client-side navigation to a second route, in the correct order |
| Dynamic imports | `LazyXxx` components and dynamic `import()` chunks load on the client after hydration, without 404s or missing asset errors |
| i18n init | Locale resolves server-side from the configured detection strategy, renders translated content in SSR HTML, and remains consistent after hydration |
| Critical CSS | Critical CSS extraction applies above-the-fold styles server-side; computed styles after hydration match the server-rendered layout within the documented tolerance |
| Console cleanliness | The browser console records **zero errors and zero hydration warnings** across the SSR→CSR transition and the initial client navigation |

### Static Generation Shakedown Path

Applications using `nuxt generate` (SSG) run a separate shakedown path in addition to the SSR+CSR path. This validates that prerendering executes without crawl errors, generated HTML matches the expected structure for every enumerated route, and client-side hydration of the prerendered markup remains mismatch-free when served from a static host. ISR routes require a third shakedown path that validates the stale-while-revalidate handoff: the first request serves the stale copy, the background regeneration completes without error, and the second request receives the fresh payload.

**SSR, SSG, and ISR each have distinct shakedown paths.** A Nuxt application that mixes rendering modes via `routeRules` validates each mode with its own known-good path. A pass on the SSR path does **not** imply a pass on the SSG path.

### Execution Principles

- **Conservative** — Use a fixture user whose dashboard response, locale, and feature flag set are documented alongside the shakedown script.
- **Progressive** — Start with the anonymous landing route (pure SSR), then the authenticated landing route (SSR + middleware + Pinia restore), then one client-side navigation, then one `useFetch`-triggered mutation. Stop at the first failure and diagnose.
- **Controlled** — Run `nuxt build` + `nuxt preview` (or the target Nitro preset output) pointed at the staging backend with sandbox credentials. **Never run shakedown against production data.**
- **Observable** — Capture the full Playwright trace, SSR response HTML, `__NUXT_DATA__` payload, browser console log, network HAR, and Pinia devtools snapshot per step.
- **Known-good inputs** — The fixture user, the expected SSR HTML shape, and the expected payload keys are part of the shakedown script, checked into source control alongside it.
- **No optimization** — Note performance issues (payload size, slow SSR, chunk size), log them, move on. Shakedown validates correctness, not quality.

### Execution Pattern

Concrete execution sequence for a Nuxt 3 shakedown.

```ts
// 1. Preflight: nuxt build passes with zero warnings, type check passes, runtimeConfig keys resolve
// 2. Start the built artifact: nuxt preview (or the deployed Nitro preset output)
// 3. Launch Playwright in headless Chromium with trace, console, and network capture enabled
// 4. Request the landing route with curl or fetch, assert the response is a 200 with complete SSR HTML
// 5. Parse __NUXT_DATA__ from the HTML, assert the expected useAsyncData keys are present and typed
// 6. Navigate to the same landing route in Playwright, assert zero "Hydration node mismatch" warnings
// 7. Assert Pinia auth store hydrated with the fixture user identity (reading the devtools snapshot)
// 8. Navigate client-side to a second critical route, assert route middleware fired once, not twice
// 9. Assert the dynamic import chunk for the second route loaded with a 200 response
// 10. Trigger a useFetch mutation via a button click, assert the POST reached the staging backend
// 11. Assert console.error and console.warn counts are zero across the full run
// 12. For SSG mode: run nuxt generate, serve .output/public statically, repeat steps 3-11 against the static output
// 13. Record artifacts and classify the result
```

### Shakedown Canary Component

```vue
<!-- shakedown canary component used only during shakedown runs -->
<script setup lang="ts">
import { onMounted } from 'vue'
import { useRuntimeConfig } from '#imports'

const config = useRuntimeConfig()
const { data, error } = await useFetch<{ build: string }>(
  '/api/shakedown/fingerprint',
  { key: 'shakedown:fingerprint' }
)

onMounted(() => {
  // Assert the build fingerprint matches the deployed artifact
  if (!data.value || data.value.build !== config.public.buildId) {
    throw new Error('Shakedown: build fingerprint mismatch')
  }
})
</script>

<template>
  <ClientOnly>
    <div v-if="error" data-shakedown="fingerprint-error">{{ error.message }}</div>
    <div v-else data-shakedown="fingerprint-ok">{{ data?.build }}</div>
  </ClientOnly>
</template>
```

### Result Classification

| Outcome | Trigger |
|:--------|:--------|
| **pass** | Every validation category held across the SSR path (and the SSG path where applicable). The bundle is cleared to proceed to the broader test suite and deployment |
| **fail-blocking** | Nitro failed to start, SSR returned a 500, hydration mismatch warnings appeared, a route middleware fired twice on SSR, or Pinia state diverged between server and client. **Fix the root cause and re-run from step 1** |
| **fail-nonblocking** | A deprecation warning appeared, the SSR payload was larger than the documented budget, or a non-critical chunk was slower than expected. Log with full reproduction context and proceed with caution |
| **inconclusive** | The staging backend returned an unexpected payload unrelated to the change, or a locale file failed to load due to environment misconfiguration. Adjust and re-run the affected validation |

### Required Artifacts

Every Nuxt shakedown run must produce and preserve:

- **SSR HTML** — Raw SSR HTML response for the landing route.
- **Nuxt payload** — Extracted `__NUXT_DATA__` payload with the keys present at the time of shakedown.
- **Playwright trace** — Trace including console, network HAR, and screenshots per step.
- **Pinia snapshot** — Store snapshot after hydration, demonstrating server-to-client state parity.
- **Result summary** — Pass/fail classification per validation category across SSR, CSR, and (where applicable) SSG paths.
- **Issue list** — Every anomaly observed, classified blocking/non-blocking/deferred, with reproduction context.
- **Environment snapshot** — Nuxt version, Nitro version, Vue version, Vite version, Nitro preset, Node version, bundle hash, staging backend URL, i18n locale list, feature flag provider build id.

### Anti-Patterns

- Skipping shakedown after a "small" server middleware reorder. Middleware order changes are among the highest-risk integration changes in a Nuxt application.
- Expanding shakedown into a comprehensive Playwright test suite with dozens of routes and assertions.
- Running shakedown against `nuxt dev` instead of `nuxt preview` or the deployed preset output.
- Running shakedown with a mocked backend, MSW, or a local in-memory stub.
- Passing the SSR path and skipping the SSG path on an application that ships via `nuxt generate`.
- Pausing shakedown to optimize SSR response time, payload size, or chunk boundaries.
- Discarding the Playwright trace, SSR HTML, or Pinia snapshot after the run.
- Treating hydration mismatch warnings as acceptable noise during a shakedown run. **Every hydration mismatch is a blocking fault.**

---
[Back to Overview](./OVERVIEW.md)
