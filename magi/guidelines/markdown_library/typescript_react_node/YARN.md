# Yarn 4 Package Management

**Yarn 4 (Berry)** is the current stable version. Complete rewrite from Yarn 1.x (Classic, in maintenance mode). Provides Plug'n'Play (PnP) for zero-install workflows, strict dependency resolution, workspaces for monorepos, significant performance improvements. Install via Corepack (bundled with Node.js).

### Corepack for Yarn Management

```bash
corepack enable
```

Declare the Yarn version in `package.json`:

```json
{
  "packageManager": "yarn@4.6.0"
}
```

Corepack downloads and caches the exact version. **Do not install Yarn globally via `npm install -g yarn`** — that installs Yarn 1.x Classic, not Berry.

### Lockfile Discipline

- Commit `yarn.lock` to version control.
- Run `yarn install --immutable` in CI to fail the build if the lockfile is out of date.
- **Never run `yarn install` without `--immutable` in CI** — it may modify the lockfile and produce non-deterministic builds.

### Pin Exact Versions

```json
{
  "dependencies": {
    "react": "19.2.0"
  }
}
```

Do **not** use `^` or `~` ranges for production application dependencies. Lockfiles provide determinism for direct installs, but version ranges affect transitive resolution and create surprising upgrades. **Use `yarn up` to update specific packages deliberately.**

### `nodeLinker` Choice

Use Yarn's `node_modules` linker (`nodeLinker: node-modules` in `.yarnrc.yml`) if PnP compatibility issues arise. PnP (the default) eliminates `node_modules` entirely and provides stricter resolution, but some packages may not work. **`node_modules` linker provides Yarn 4's performance and features with traditional resolution.**

### Workspaces for Monorepos

```json
{
  "workspaces": ["packages/*", "apps/*"]
}
```

Hoist shared dependencies, enable cross-package imports with `workspace:` protocol, run scripts across all packages with `yarn workspaces foreach`. **Enforce consistent dependency versions across workspaces using constraints.**

### `yarn dlx` Over `npx`

```bash
yarn dlx create-react-app my-app
yarn dlx typecheck
```

`dlx` uses Yarn's cache and resolution, ensuring consistent behavior with the project's package manager.

---
[Back to Overview](./OVERVIEW.md)
