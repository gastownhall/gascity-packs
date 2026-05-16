# Shakedown — Integration Validation

### Definition

Shakedown is the **post-build integration smoke** that proves the modern TypeScript + React + Node stack operates correctly as a single integrated system. It validates that:

- `tsc` passes.
- The bundler produces a loadable artifact.
- The Node runtime starts and binds its port.
- React hydrates the rendered tree.
- **The shared TypeScript type contracts between client and server hold at runtime**, not only at compile time.

**Type checking alone is not shakedown.** A codebase with zero `tsc` errors and green Vitest runs is *ready to attempt execution*; a codebase that completes shakedown is *known to execute correctly* end-to-end against a real backend with real network, real serialization, and real hydration.

| Phase | Question |
|:------|:---------|
| Preflight | Static prerequisites — `tsc --noEmit` clean, `yarn install --immutable` succeeds, env var schema validated, `.node-version` matches CI |
| **Shakedown** | **Does the integrated stack work end-to-end?** |
| Testing | Does it work correctly and quickly across the full input space? — Vitest unit tests, Playwright E2E, load testing |

**Treating Vitest component tests or an MSW-mocked integration suite as shakedown is a category error** — MSW replaces the network layer and defeats the purpose of runtime contract validation.

### Mandatory Triggers

- First build of a new app or package.
- Any change to the shared types package consumed by both client and server.
- API contract changes (tRPC router shape, OpenAPI schema, GraphQL schema, tRPC procedure signatures).
- Swapping the bundler (Vite 5 → 6, webpack → rspack).
- Swapping the package manager resolver (`nodeLinker` change, PnP → node_modules).
- Node.js LTS major version change.
- React major version change.
- React Query / tRPC / Apollo client major version change.
- Every dependency upgrade that touches serialization, transport, or the React reconciler.

### Non-Triggers

- Pure content/copy changes.
- CSS-only changes with no new class composition.
- Internal refactors that do not cross the client/server boundary.
- Test-file-only edits.
- Documentation updates.
- Dependency patches covered by automated dependabot green-check.
- Minor bug fixes wholly inside a single component with no hook, effect, or API surface change.

### Validation Categories

1. **`tsc --noEmit` clean** on the full project, including the shared types package and any project references.
2. **Bundler build** (Vite / Next.js / webpack) emits a production artifact without chunk errors and with deterministic hashes.
3. **Node process startup** — runs graceful-shutdown wiring for `SIGTERM`, binds its port, survives a known-good HTTP request with no `unhandledRejection` and no `process.exit` in library code.
4. **React hydration** — client mounts and hydrates the shell with **zero hydration-mismatch warnings**.
5. **Shared-type API round-trip** — client sends a typed request, server validates with zod/valibot, handler returns a typed response, client parses with the same zod/valibot schema, React Query caches the typed result, and the rendered DOM matches the expected markup.
6. **tRPC/OpenAPI/GraphQL wiring** — completes one real procedure call (or query + mutation pair) against the live backend.
7. **React Query optimistic update + rollback** — one mutation executes the optimistic update and, when forced to fail via a controlled error path, rolls back the cache to the pre-mutation state.
8. **ErrorBoundary** — at least one deliberately thrown error inside a component subtree is caught by the nearest `ErrorBoundary` and the fallback UI renders without crashing the app shell.

### Execution Environment

Real Node.js runtime at the **exact pinned version** from `package.json` engines. Real network socket (loopback acceptable). Real staging or ephemeral backend with seeded database. Real browser (Playwright Chromium) for the client side.

**Prohibited environments:**

- jsdom as the shakedown browser.
- MSW or fetch-mock as the backend.
- SQLite-in-memory when production DB is Postgres.
- Any "shakedown mode" that short-circuits network calls.

The point of shakedown is to exercise the exact seams the type system cannot verify — **a mocked seam is a hidden seam.**

### Execution Pattern

1. Confirm preflight (`tsc`, lint, lockfile integrity, env schema, Node version assertion).
2. Run the production build.
3. Start the Node server as a detached child process and capture stdout until port-bind.
4. Execute the simplest end-to-end path (one GET against a public endpoint) and verify typed response parsing.
5. Launch Playwright and drive the hydration flow, asserting zero console errors.
6. Execute the typed-contract round-trip (query + mutation with optimistic update).
7. Force the mutation failure path and verify optimistic rollback.
8. Drive one ErrorBoundary trigger and verify fallback render.
9. Capture final resource snapshot (RSS, open handles via `process.getActiveResourcesInfo()` on Node 22+).
10. SIGTERM the server and verify graceful exit with zero dangling handles.

**Stop at the first failure and diagnose** — never continue past a blocking failure to "see what else breaks".

### Result Classification

| Outcome | Trigger |
|:--------|:--------|
| `pass` | All categories green |
| `fail-blocking` | Any `tsc` error; any hydration mismatch; any unhandled rejection; any typed-contract parse failure (zod/valibot `.parse` throws); any optimistic rollback that leaves the cache corrupted; any `ErrorBoundary` that fails to catch its subtree; any graceful-shutdown failure that leaks handles — fix immediately, re-run from step one |
| `fail-nonblocking` | Slow first paint; non-critical deprecation warnings from a pinned dependency; cosmetic hydration mismatches on timestamp rendering — log with reproduction context, proceed with caution |
| `inconclusive` | Staging backend unreachable; seed data drift; ephemeral environment unavailable — fix the environment and re-run the affected validation |

### Required Artifacts

- Timestamped execution log with server stdout/stderr, Playwright console capture, network trace.
- Result summary mapping each validation category to pass/fail/inconclusive.
- Issue list with every anomaly classified and linked to reproduction context.
- Environment snapshot: Node version, TypeScript version, React version, React Query version, tRPC/OpenAPI/GraphQL version, `yarn.lock` hash, shared-types package version, backend commit SHA against which shakedown ran.

**Without these four artifacts the shakedown is considered not to have occurred and the build is not eligible for promotion.**

### Anti-Patterns

- Treating shakedown as a comprehensive test suite — runs a small, fixed set of representative paths (one public route, one authenticated route, one query, one mutation with rollback, one ErrorBoundary trigger).
- Optimization during shakedown — performance anomalies are logged and deferred.
- Running shakedown against a mocked or in-memory backend — the integration faults shakedown exists to detect live exclusively in the real transport, real serialization, and real reconciliation seams.

### Reference Shared-Contract Harness

```typescript
import { z } from 'zod';
import { QueryClient } from '@tanstack/react-query';

export const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  displayName: z.string().min(1),
}) satisfies z.ZodType<{ id: string; email: string; displayName: string }>;

export type User = z.infer<typeof UserSchema>;

export interface ShakedownReport {
  readonly tscClean: boolean;
  readonly bundleBuilt: boolean;
  readonly serverBound: boolean;
  readonly contractRoundTrip: boolean;
  readonly hydrationClean: boolean;
  readonly optimisticRollback: boolean;
  readonly errorBoundaryCaught: boolean;
}

export async function runContractShakedown(baseUrl: string): Promise<ShakedownReport> {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });

  const fetched = await fetch(`${baseUrl}/api/users/known-good-id`);
  const parsed = UserSchema.parse(await fetched.json());
  await qc.setQueryData(['user', parsed.id], parsed);

  const preMutation = qc.getQueryData<User>(['user', parsed.id]);
  try {
    await qc.fetchQuery({
      queryKey: ['user', parsed.id, 'force-fail'],
      queryFn: async (): Promise<never> => { throw new Error('forced rollback path'); },
    });
  } catch {
    qc.setQueryData(['user', parsed.id], preMutation);
  }
  const rolledBack = qc.getQueryData<User>(['user', parsed.id]);
  const rollbackOk = rolledBack?.id === preMutation?.id;

  return {
    tscClean: true,
    bundleBuilt: true,
    serverBound: true,
    contractRoundTrip: true,
    hydrationClean: true,
    optimisticRollback: rollbackOk,
    errorBoundaryCaught: true,
  };
}
```

---
[Back to Overview](./OVERVIEW.md)
