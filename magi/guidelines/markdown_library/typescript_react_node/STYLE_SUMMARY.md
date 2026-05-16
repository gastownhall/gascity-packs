# Style Summary

| Element | Required Style |
|:--------|:---------------|
| TypeScript | `strict: true` + `noUncheckedIndexedAccess`; no `any`; `unknown` + narrow; discriminated unions for state; `satisfies` for validation; branded types for IDs; `readonly` by default; zod at boundaries |
| React Components | Function components only; typed props exported; single responsibility; React 19 Actions for forms; `use()` for promises; Server Components default in frameworks; Compiler handles memoization |
| Hooks | Rules of Hooks enforced; `useState` typed explicitly when needed; `useEffect` for external sync only; `useEffectEvent` for stable handlers; custom hooks for reuse; typed return objects |
| State Management | Server state via TanStack Query/SWR; client state via Zustand/Jotai or `useState`; context for DI not global state; `useReducer` with discriminated union actions for complex state |
| Node.js | Node 22+ LTS; ESM with `"type": "module"`; `node:` prefix on builtins; graceful shutdown on SIGTERM; unhandled rejection handler; native TypeScript execution for dev |
| Yarn 4 | Corepack for version management; `"packageManager"` in `package.json`; `yarn.lock` committed; `--immutable` in CI; exact version pins; workspaces for monorepos; `dlx` over `npx` |
| Error Handling | No empty catches; `unknown` in catch clauses; Error Boundaries in React; structured HTTP errors in Node; Result types for expected failures |
| Async | `async`/`await` over `.then` chains; `Promise.allSettled` for independent operations; `AbortController` for cancellation; `Promise.withResolvers` for external resolution |
| Testing | Vitest or Jest; React Testing Library for behavior tests; MSW for API mocking; typed mocks; supertest for HTTP endpoint tests |
| Shakedown | Real Node + real browser + real backend; pass / fail-blocking / fail-nonblocking / inconclusive; four artifacts (log, summary, issues, env snapshot) |
| Linting | ESLint + `typescript-eslint` `strict-type-checked`; Prettier for formatting; React Compiler plugin; `lint-staged` pre-commit; `tsc --noEmit` in CI |
| Security | No `dangerouslySetInnerHTML` unsanitized; zod validation at boundaries; no secrets in public env vars; `yarn audit` in CI; helmet for Node.js HTTP headers |
| Performance | Route-level code splitting; bundle analysis; streaming in Node.js and React SSR; `useTransition`/`useDeferredValue` for concurrent UX; measure before optimize |
| Structure | Feature-based organization; monorepo with `packages/` and `apps/`; path aliases; TypeScript project references; colocation of component + test + types |
| Defense in Depth | Strict tsc + ESLint + runtime zod + unit/component tests + E2E browser tests + CI preview deploys + shakedown |
| Rule of Three | tsc + runtime zod validation + E2E browser tests MUST agree before declaring done |

---
[Back to Overview](./OVERVIEW.md)
