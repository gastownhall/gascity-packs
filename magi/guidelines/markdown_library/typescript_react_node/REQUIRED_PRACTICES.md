# Required Practices

### Always Do

- Enable `strict: true` plus `noUncheckedIndexedAccess` and `exactOptionalProperties` in `tsconfig.json`.
- Use discriminated unions for state modeling. Prevent impossible states via type structure.
- Validate all external data (API responses, request bodies, config) with zod/valibot at trust boundaries.
- Use function components with TypeScript for all React components. Export typed props.
- Follow the Rules of Hooks unconditionally. Enforce with `eslint-plugin-react-hooks`.
- Extract reusable stateful logic into custom hooks with typed return values.
- Wrap component subtrees in Error Boundaries. Handle async errors in all data fetching.
- Use ESM (`"type": "module"`) for all new Node.js code. `node:` prefix on built-in imports.
- Pin the Node.js version per project via `.node-version`, `.nvmrc`, or `engines` field.
- Use Corepack with `"packageManager"` in `package.json` for Yarn version management.
- Commit `yarn.lock` to version control. Use `--immutable` in CI.
- Use ESLint with `typescript-eslint` `strict-type-checked` preset. Prettier for formatting.
- Use React Testing Library for component tests. Test behavior, not implementation.
- Handle `SIGTERM`/`SIGINT` in Node.js servers for graceful shutdown.
- Use `AbortController` for cancellable async operations. Cancel on unmount and navigation.
- Run `yarn audit` in CI. Address high/critical vulnerabilities before deployment.
- Code-split at the route level minimum. Target under 200KB initial JS gzipped.
- Run a §11 shakedown after every triggering change before promotion.

---
[Back to Overview](./OVERVIEW.md)
