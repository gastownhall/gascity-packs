# Prohibited Practices

### Never Do

- Use `any` type anywhere in codebase.
- Suppress TypeScript errors with `@ts-ignore` or `@ts-expect-error`.
- Store server state in Zustand or component state.
- Create components larger than 200 lines.
- Use index as `key` in lists.
- Mutate state directly.
- Use inline styles except for truly dynamic values.
- Import entire libraries (`import * as`).
- Use `var` for variable declarations.
- Use class components except for `ErrorBoundary`.
- Fetch data in `useEffect` when TanStack Query is available.
- Use non-semantic `div`/`span` when a semantic element exists.
- Commit code with `console.log` statements.
- Leave TODOs or placeholder code.
- Use deprecated React features (e.g., `componentWillMount`).
- Mix concerns in a single component.
- Use magic numbers without constants.
- Ignore accessibility requirements.
- Construct dynamic Tailwind class names via string concatenation.
- Use `@apply` in component files.
- Run shakedown against the dev server.

---
[Back to Overview](./OVERVIEW.md)
