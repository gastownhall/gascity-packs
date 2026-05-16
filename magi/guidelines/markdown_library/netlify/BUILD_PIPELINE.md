# Build Pipeline

### Build Command Discipline

The build command runs in Bash. Keep build commands simple; delegate complexity to npm scripts.

| Acceptable | Forbidden |
|:-----------|:----------|
| `npm run lint && npm run test && npm run build` | Four lines of inline Bash with `sed`, `awk`, conditional file copies |

Move complex logic into a script file and call the script.

### Build Plugins

Netlify build plugins hook into the build lifecycle at defined stages:

- `onPreBuild`
- `onBuild`
- `onPostBuild`
- `onSuccess`
- `onError`
- `onEnd`

Community and custom plugins install via npm. Netlify-maintained plugins are available without explicit installation. **Audit every third-party plugin before adoption** — plugins execute with full access to the build environment, including environment variables.

```toml
[[plugins]]
  package = "@netlify/plugin-lighthouse"
  [plugins.inputs]
    audits = ["performance", "accessibility"]
```

### Build Caching

Netlify caches the `node_modules` directory between builds. The cache key is derived from the lockfile hash. Changes to `package-lock.json`, `yarn.lock`, or `pnpm-lock.yaml` invalidate the cache.

**Do not rely on build cache for application state** — the cache is a performance optimization for dependency installation, not a persistence layer. Build cache can be cleared at any time via the UI or API without warning.

### Ignore Builds

Configure the `ignore` command to skip unnecessary builds and save build minutes. Exit code 0 = skip; non-zero = proceed. Critical for monorepos and documentation sites where most commits do not affect the deployed output.

```toml
[build]
  ignore = "git diff --quiet $CACHED_COMMIT_REF $COMMIT_REF -- src/ public/ netlify.toml"
```

### Runtime Version Pinning

Pin every runtime version. Unpinned versions are the leading cause of build failures across Netlify projects — the build image updates independently of your repository.

| Runtime | Pin Location |
|:--------|:-------------|
| Node.js | `NODE_VERSION` in `netlify.toml` or `.nvmrc` |
| Ruby | `RUBY_VERSION` in `netlify.toml` or `.ruby-version` |
| Python | `PYTHON_VERSION` in `netlify.toml` or `runtime.txt` |
| Go | `GO_VERSION` in `netlify.toml` |
| Hugo | `HUGO_VERSION` in `netlify.toml` |

---
[Back to Overview](./OVERVIEW.md)
