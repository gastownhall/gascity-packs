# Prohibited Practices

### Never Do

- Use the `any` type. Use `unknown` and narrow with type guards.
- Write new class components. All new components are function components.
- Use `// @ts-ignore` or `// @ts-expect-error` without a justification comment and tracking issue.
- Disable strict mode or any strict sub-flag in `tsconfig.json`.
- Use `defaultProps` on function components — use destructuring defaults in the function signature.
- Use `React.FC` or `React.FunctionComponent` for component typing — use typed props directly.
- Use raw `useEffect` + `useState` + `fetch` for server data — use TanStack Query or SWR.
- Disable the `react-hooks/exhaustive-deps` ESLint rule. Fix the dependencies instead.
- Use `dangerouslySetInnerHTML` without DOMPurify sanitization.
- Store server-side secrets in `NEXT_PUBLIC_`, `VITE_`, or client-accessible environment variables.
- Use Enzyme for testing — use React Testing Library.
- Use Create React App for new projects — use Vite.
- Use `<div>` or `<span>` with `onClick` for interactive elements — use `<button>`, `<a>`, or appropriate semantic HTML.
- Deploy without error boundaries around route-level and third-party component sections.
- Add `useMemo`, `useCallback`, or `React.memo` without profiling evidence of a performance problem.
- Run production systems on Node 16 or any EOL Node.js version. **Upgrade to Node 20 LTS or later.**
- Run shakedown against jsdom, mocked fetch, an in-memory backend, or a bundler dev server.

---
[Back to Overview](./OVERVIEW.md)
