# Shakedown — Integration Validation

### Definition

Shakedown is the **first controlled, end-to-end execution of the React + Node 16 stack as an integrated whole** after a build. It answers one question: **does the SSR server + CSR client + backend API actually function when everything runs together?**

Shakedown sits between:

- **Preflight** — static checks (`tsconfig` parses, `node_modules` resolve, env vars defined).
- **Production testing** — RTL component tests, Lighthouse, accessibility audits.

A bundle that passes `tsc` and Jest is **ready to attempt execution**. A bundle that passes shakedown is **known to hydrate, fetch, and render correctly** against a real backend on the frozen Node 16 runtime.

### Mandatory Triggers

Shakedown is mandatory after:

- The first-ever build of a new app.
- Any change to the SSR entry (`renderToString` / `renderToPipeableStream`), client hydration entry (`hydrateRoot`), or React Query `QueryClient` configuration.
- Webpack/Vite config changes that affect chunking or polyfill injection.
- Upgrades to React, React Router, React Query, or any library that must remain Node 16 compatible.
- Changes to the auth cookie contract or the API client base URL.
- Every applied security patch to a dependency that pinned Node 16 support — Node 16 reached EOL on **September 11, 2023** and receives zero upstream security patches; any backported security-critical dependency carries elevated risk and demands a fresh shakedown before the artifact is promoted.

### Non-Triggers

- Pure copy or translation string updates that do not change component structure.
- Pure CSS/Tailwind class adjustments with no new dynamic class composition.
- Content-only JSON data updates.
- Test-only file changes.
- README/documentation edits.

Routine execution is handled by the existing CI test matrix, not by shakedown.

### Failure Surfaces Validated

Shakedown validates the following failure surfaces unique to the Node 16 + React stack:

1. The Node 16 server process starts with the production bundle, binds the configured port, and survives a known-good HTTP request without an `unhandledRejection`.
2. The SSR entry renders the application shell with a known-good data payload and emits **zero hydration-mismatch warnings** when the client reattaches.
3. The client bundle hydrates and the React Query cache rehydrates from the server-inlined dehydrated state.
4. The auth context hydrates from cookies provided by the **real** backend (not a mocked auth stub) and resolves to an authenticated user object.
5. At least one representative API round-trip (`fetch` → backend → JSON deserialize → React Query cache → rendered DOM) succeeds against the real backend, not a mock or in-memory fixture.
6. Legacy polyfills required by the Node 16 runtime constraint (fetch via `undici` pinned to a Node-16-compatible major, `AbortController` shim, `ReadableStream` polyfill where used) load without `ReferenceError` on the server and without duplicate-global warnings on the client.
7. The browser console captures **zero React errors and zero hydration warnings** across the entire happy-path route graph.

### Execution Conditions

Execute shakedown under conservative conditions:

- A single representative user session with a single representative dataset.
- Against a staging backend with known-good seed data.
- On a runtime image that exactly matches production (Node 16.x patch version pinned in `.nvmrc` and `engines` field).
- Run the full production build command (not the dev server).
- Start the production server binary.
- Drive the client through a real browser (Chromium headless is acceptable).

**Do not run shakedown against** a mocked API, jsdom-only environment, or bundler dev server — these environments hide hydration and SSR bugs that only surface in the production pipeline.

### Execution Order

1. Confirm preflight passes: `tsc --noEmit` clean, lockfile integrity, Node 16 version assertion, required env vars present.
2. Build the SSR and client bundles with production flags.
3. Launch the Node 16 server binary and capture the startup log until the port-bound line is emitted.
4. Issue a known-good HTTP GET against the index route and verify HTTP 200 with SSR markup containing the expected shell sentinel.
5. Drive a headless browser to the same URL, wait for hydration completion, assert zero console errors, and assert the React Query devtools-visible cache contains the rehydrated entries.
6. Exercise the auth-gated flow with a known-good cookie and assert the authenticated view renders.
7. Capture the resource snapshot (open file descriptors, memory RSS).
8. Shut down gracefully via `SIGTERM` and assert zero orphan child processes.

### Result Classification

| Outcome | Trigger |
|:--------|:--------|
| `pass` | Every category green; no warnings, no orphans |
| `fail-blocking` | Hydration mismatch warning; any console error; `unhandledRejection` on the server; failed API round-trip; auth context resolving to `null` with valid cookies; SSR markup missing the expected shell sentinel — code fix and full shakedown re-run from step one |
| `fail-nonblocking` | Slow first paint that does not break correctness; non-critical deprecation warnings from a pinned dependency — log to issue tracker with reproduction context |
| `inconclusive` | Staging backend unreachable; seed data stale — fix the environment and re-run only the affected validation |

### Required Artifacts

Every shakedown produces four artifacts stored alongside the build in a retrievable location:

1. The full timestamped server + browser console log.
2. A result summary classifying each validation category.
3. An issue list with every warning and anomaly classified blocking/non-blocking/deferred.
4. An environment snapshot capturing the exact Node 16 patch version, React version, React Query version, lockfile hash, and the dehydrated state payload used as the known-good input.

The snapshot establishes the **validated baseline** — the next shakedown diffs against it to detect drift. **A shakedown without these four artifacts is treated as a shakedown that never happened.**

### Anti-Patterns

- Treating shakedown as a test suite — it runs a small number of representative paths (typically the index route, one authenticated route, one data-fetching route) with known-good inputs where correct output is known in advance. Expanding shakedown to dozens of assertions converts it into slow, duplicated coverage that belongs in Jest/Vitest or Playwright.
- Optimizing during shakedown — performance anomalies are logged and deferred to the performance testing phase.
- Running shakedown against a non-representative environment (jsdom, mocked fetch, in-memory database) — the failures shakedown exists to catch live exclusively in the real integration surface.

### Reference Harness

Minimal shakedown harness for the React + Node 16 stack. Drives the built production server through one representative route and captures console errors, hydration warnings, and the dehydrated React Query cache.

```typescript
import { chromium, type ConsoleMessage } from 'playwright';
import { spawn, type ChildProcess } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';

interface ShakedownResult {
  readonly passed: boolean;
  readonly consoleErrors: ReadonlyArray<string>;
  readonly hydrationWarnings: ReadonlyArray<string>;
  readonly ssrStatus: number;
  readonly authResolved: boolean;
}

async function runShakedown(serverPort: number, authCookie: string): Promise<ShakedownResult> {
  const server: ChildProcess = spawn('node', ['./dist/server/index.js'], {
    env: { ...process.env, PORT: String(serverPort), NODE_ENV: 'production' },
    stdio: 'pipe',
  });
  await waitForPortBind(server, serverPort);

  const ssrResponse = await fetch(`http://127.0.0.1:${serverPort}/`);
  const ssrStatus = ssrResponse.status;

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  await context.addCookies([{ name: 'auth', value: authCookie, domain: '127.0.0.1', path: '/' }]);
  const page = await context.newPage();

  const consoleErrors: string[] = [];
  const hydrationWarnings: string[] = [];
  page.on('console', (msg: ConsoleMessage): void => {
    const text = msg.text();
    if (msg.type() === 'error') { consoleErrors.push(text); }
    if (text.includes('Hydration') || text.includes('did not match')) { hydrationWarnings.push(text); }
  });

  await page.goto(`http://127.0.0.1:${serverPort}/`, { waitUntil: 'networkidle' });
  const authResolved = await page.evaluate((): boolean =>
    Boolean((window as unknown as { __AUTH__?: { userId: string } }).__AUTH__?.userId),
  );

  await browser.close();
  server.kill('SIGTERM');
  await delay(500);

  return {
    passed: ssrStatus === 200 && consoleErrors.length === 0 && hydrationWarnings.length === 0 && authResolved,
    consoleErrors,
    hydrationWarnings,
    ssrStatus,
    authResolved,
  };
}

function waitForPortBind(proc: ChildProcess, port: number): Promise<void> {
  return new Promise((resolve, reject): void => {
    const timer = setTimeout((): void => reject(new Error(`Port ${port} bind timeout`)), 15000);
    proc.stdout?.on('data', (chunk: Buffer): void => {
      if (chunk.toString().includes(`listening on ${port}`)) { clearTimeout(timer); resolve(); }
    });
  });
}
```

---
[Back to Overview](./OVERVIEW.md)
