# Style Summary

| Element | Required Style |
|:--------|:---------------|
| File Structure | `components/`, `pages/`, `hooks/`, `services/`, `store/`, `types/`, `utils/`, `styles/` |
| Component Type | Functional components with TypeScript; max 150 lines, complexity ≤ 10 |
| Props | Explicit interfaces; never `any` type |
| TypeScript | Strict mode; `noUncheckedIndexedAccess`; `satisfies` operator; const generics |
| React Version | React 18.3+ patterns; React 19 `use()` hook + Suspense; Compiler-compatible |
| State Management | TanStack Query for server state; Zustand (slices + immer + devtools + persist) for client state |
| Forms | React Hook Form + Zod resolver; `useFieldArray` for dynamic; refine for cross-field rules |
| Routing | React Router v6 with lazy loading and `Suspense` |
| Styling | Tailwind CSS; centralized theme; `clsx` for conditionals; `cva` for variants; no dynamic class strings |
| Performance | `memo` / `useMemo` / `useCallback` per decision tree; intersection observer for lazy visibility; chunk ≤ 200KB; initial bundle ≤ 100KB |
| Error Handling | Granular boundaries (App + Feature); explicit loading/error/empty states; optimistic updates with rollback |
| Accessibility | WCAG 2.1 AA; semantic HTML; ARIA; focus trap; 4.5:1 contrast; `axe-core` automated |
| Testing | 90%+ coverage; Vitest + Testing Library (user-centric queries) + MSW + Playwright E2E |
| Build Pipeline | Zero errors, zero warnings; Lighthouse 90+; bundle budgets enforced |
| Environment | `import.meta.env` validated through Zod schema at boot |
| Imports | Ordered groups with path aliases; alphabetical within groups |
| Deployment | Docker multi-stage build with Nginx; SPA fallback; gzip; immutable cache for hashed assets |
| Shakedown | Production bundle in real browser; Playwright trace + HAR; classify pass / fail-blocking / fail-nonblocking / inconclusive |
| Defense in Depth | Type-check + lint + unit/component tests + runtime schema validation + E2E + a11y audit + preview smoke |
| Rule of Three | Type checker + tests + real-browser E2E on a deployed preview MUST agree before declaring done |

---
[Back to Overview](./OVERVIEW.md)
