# Style Summary

| Element | Required Style |
|:--------|:---------------|
| TypeScript Config | `strict: true` + `noUncheckedIndexedAccess` + `exactOptionalProperties`; `bundler` moduleResolution; `verbatimModuleSyntax`; `isolatedModules`; ES2020+ target |
| Type System | No `any` (use `unknown`); `interface` for shapes, `type` for unions; discriminated unions for variants; `satisfies` for validation without widening; generics with constraints; zod at boundaries; minimal assertions |
| Components | Function components only; typed `interface` props; explicit `children: ReactNode`; destructuring defaults not `defaultProps`; no `React.FC`; feature-organized; single responsibility; lazy + Suspense for code-splitting |
| Hooks | Type `useState`/`useRef` generics; exhaustive `useEffect` deps; cleanup functions mandatory; custom hooks for reuse; options objects for config; Rules of Hooks enforced via ESLint |
| State Management | Client state (`useState`/`useReducer`/Zustand) separate from server state (TanStack Query); Context for low-frequency shared state; typed providers with consumer hooks; queryKey factories |
| Data Fetching | TanStack Query for all server data; zod validation on responses; handle loading/error/empty; centralized API client; request cancellation via `AbortController` |
| Forms | Form libraries (React Hook Form) for complex forms; zod schemas for validation + types; server validation always; typed form values |
| Error Handling | Error boundaries around major sections; typed errors (`unknown` in catch); discriminated error unions; report to error tracking service |
| Performance | Measure before optimize; `React.memo` for expensive stable-prop components; `useCallback`/`useMemo` only when profiled; `useTransition` for non-urgent updates; virtualize long lists; bundle analysis |
| Accessibility | Semantic HTML; keyboard-accessible interactive elements; `alt` text; `aria-label`s; focus management in SPAs; `eslint-plugin-jsx-a11y`; automated axe checks in tests |
| Testing | Vitest or Jest + React Testing Library; test behavior not implementation; MSW for API mocking; `renderHook` for custom hooks; axe-core for a11y checks |
| Shakedown | Real backend, real browser, production build; index + auth + data-fetching routes; pass / fail-blocking / fail-nonblocking / inconclusive; four artifacts (log, summary, issues, env snapshot) |
| Security | No `dangerouslySetInnerHTML` without DOMPurify; no secrets in client bundles; dependency audit in CI; sanitize user input in `href` and `style`; lockfile integrity |
| Build/Tooling | Vite for new projects; `typescript-eslint` + `react-hooks` + `jsx-a11y`; Prettier for formatting; path aliases; frozen lockfile installs; upgrade from Node 16 EOL to Node 20 LTS |
| Project Structure | Feature-based organization; `shared/` for common code; path aliases for absolute imports; barrel exports at feature boundary; co-locate tests with source |
| Defense in Depth | Strict tsc + ESLint + RTL + runtime zod + E2E browser tests + CI coverage floor + shakedown |
| Rule of Three | Type checker + component tests + browser E2E MUST all agree before a feature is "done" |

---
[Back to Overview](./OVERVIEW.md)
