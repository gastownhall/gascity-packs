# Required Practices

### Always Do

- Enable `strict: true`, `noUncheckedIndexedAccess`, `exactOptionalProperties`, and `noImplicitOverride` in `tsconfig.json`.
- Use function components with typed props for all new components.
- Use `unknown` instead of `any`. Narrow types with guards at trust boundaries.
- Use discriminated unions for state machines and variant types.
- Validate API responses with zod/valibot at fetch boundaries.
- Use TanStack Query for all server-state data fetching with typed query keys.
- Maintain exhaustive `useEffect` dependency arrays. Enable and enforce the ESLint rule.
- Return cleanup functions from `useEffect` for subscriptions, timers, listeners.
- Extract reusable stateful logic into typed custom hooks.
- Wrap major UI sections in error boundaries with fallback UI.
- Use semantic HTML elements for interactive and structural content.
- Ensure all interactive elements are keyboard-accessible.
- Provide `alt` text for all images and `aria-label` for icon buttons.
- Test components with React Testing Library. Test behavior, not implementation.
- Enable `eslint-plugin-react-hooks` rules (`rules-of-hooks`, `exhaustive-deps`) in CI.
- Commit lockfiles and install with `--frozen-lockfile` in CI.
- Run dependency vulnerability scanning in CI. Fail on high/critical severity.
- Profile with React DevTools Profiler before applying memoization or code splitting.
- Run a §13 shakedown against the real backend in a real browser after every triggering change.

---
[Back to Overview](./OVERVIEW.md)
