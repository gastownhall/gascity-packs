# Build and Tooling

Build tooling compiles TypeScript, bundles modules, optimizes assets, and enforces code quality. The tooling layer affects every developer's workflow and every deployed artifact.

### Vite for New Projects

Use **Vite** as the build tool for new React projects. Vite provides:

- Near-instant dev server startup (native ESM, no-bundle dev)
- Fast HMR
- Optimized production builds via Rollup
- First-class TypeScript support

**Create React App (CRA) is unmaintained and deprecated.** Webpack is acceptable for existing projects but should not be chosen for new projects when Vite is available.

### ESLint Configuration

Configure ESLint with:

- `typescript-eslint`
- `eslint-plugin-react`
- `eslint-plugin-react-hooks`
- `eslint-plugin-jsx-a11y`

Run ESLint in CI and fail on errors. The `react-hooks/rules-of-hooks` and `react-hooks/exhaustive-deps` rules are **non-negotiable** — they catch hook ordering violations and stale closure bugs that cause intermittent, hard-to-reproduce defects.

### Prettier

Use Prettier for code formatting. Run Prettier as a pre-commit hook (via `husky` + `lint-staged`) or in CI. Formatting debates are eliminated by automation. Configure Prettier once, never discuss indentation, semicolons, or quote style again. The team's energy goes to architecture and logic, not cosmetics.

### Lockfile Discipline

Commit lockfiles (`yarn.lock`, `package-lock.json`, `pnpm-lock.yaml`) to version control. Install from lockfiles in CI:

| Tool | Frozen install |
|:-----|:---------------|
| Yarn 1 | `yarn install --frozen-lockfile` |
| Yarn 4 | `yarn install --immutable` |
| npm | `npm ci` |
| pnpm | `pnpm install --frozen-lockfile` |

**Never run install commands that modify the lockfile during CI builds.** A modified lockfile in CI means the build is non-deterministic.

### Yarn 1.22 Migration

Yarn Classic (1.x) is in maintenance mode. **Yarn 4 (Berry)** provides PnP for zero-install, faster installs, plugin architecture, and workspace improvements. **pnpm** is another high-performance alternative with strict dependency isolation that prevents phantom dependencies. Evaluate migration from Yarn 1.22 to Yarn 4 or pnpm for improved performance and security. If remaining on Yarn 1.22, ensure the lockfile integrity check (`--frozen-lockfile`) is enforced in all CI pipelines.

---
[Back to Overview](./OVERVIEW.md)
