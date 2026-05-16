# Monorepo Configuration

### Structure

Each site in the monorepo gets its own Netlify site linked to the same repository, each with its own `netlify.toml`.

**Best practice:** one `netlify.toml` per site, located in the site's package directory. Root-level configuration applies to all sites and should contain only shared settings (if any).

### Package vs Base Directory

| Setting | Purpose |
|:--------|:--------|
| Base directory | Where Netlify installs dependencies and runs the build command. Set to the workspace root if using workspace-level dependency installation |
| Package directory | Where Netlify looks for `netlify.toml` and site-specific configuration. Set to the specific package directory (e.g., `packages/web`) |

Paths in `netlify.toml` are relative to the base directory.

### Build Filtering

Use the `ignore` command aggressively in monorepos. Without it, every push triggers builds for every linked site, even when only one package changed. **Include shared package directories in the diff check** — a change to a shared utility library must trigger rebuilds for sites that consume it.

```toml
[build]
  ignore = "git diff --quiet $CACHED_COMMIT_REF $COMMIT_REF -- packages/web/ shared/"
```

---
[Back to Overview](./OVERVIEW.md)
