# Prohibited Practices

### Never Do

- Use the `any` type. Use `unknown` and narrow with type guards.
- Use `@ts-ignore` or `@ts-expect-error` in production code.
- Use type assertions (`as`) without accompanying runtime validation at trust boundaries.
- Write new React class components. Use function components with hooks.
- Write empty `catch` blocks. Log, re-throw, or handle every caught error.
- Use `dangerouslySetInnerHTML` with unsanitized input.
- Store secrets in `NEXT_PUBLIC_`, `VITE_`, or `EXPO_PUBLIC_` prefixed environment variables.
- Use Yarn 1.x (Classic) for new projects. Use Yarn 4 (Berry) via Corepack.
- Install Yarn via `npm install -g yarn`. Use Corepack.
- Use version ranges (`^`, `~`) for production application dependencies. Pin exact versions.
- Use `process.exit()` in library code or middleware. Throw errors instead.
- Write new Node.js code in CommonJS (`require`/`module.exports`). Use ESM.
- Add `useMemo`/`useCallback` where the React Compiler handles memoization. Profile before manual optimization.
- Use `useEffect` for data fetching when TanStack Query, SWR, or framework data loaders are available.
- Test component implementation details (state values, hook calls) instead of behavior (user interactions, rendered output).
- Import entire utility libraries (`import _ from 'lodash'`). Import specific functions from tree-shakeable packages.
- Skip the §11 shakedown after a triggering change.
- Run shakedown against MSW, jsdom, or any mocked seam.

---
[Back to Overview](./OVERVIEW.md)
